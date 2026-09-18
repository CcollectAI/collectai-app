/**
 * A cast is not a mapping.
 *
 * `listMarketplaceSales` was `unwrap<MarketplaceSale>(...)` — the server's
 * snake_case payload asserted to be a camelCase type. At runtime every
 * `salePrice` and `netProceeds` was `undefined`, and the Sales tab's Revenue
 * Summary sums them, so it would have rendered **NaN** for gross and net.
 *
 * It had never been seen because `marketplace_sales` held 0 rows for the life
 * of the marketplace (measured on production 2026-09-18) — nothing wrote one
 * until a completed trade started recording the seller's sale. That is what
 * turned this from dormant into about-to-ship, and it is why the first row
 * written by a new writer is worth a test of the READ path too.
 */
import {
  listMarketplaceSales,
  getMarketplaceFeeSchedules,
} from '../../src/data/providers/dealsProvider';

const mockGet = jest.fn();

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: { get: (...a: unknown[]) => mockGet(...a) },
}));

/** Exactly what `SaleResponse` serialises (marketplace_listing_router.py). */
function serverSale(over: Record<string, unknown> = {}) {
  return {
    id: 's-1',
    listing_id: 'l-1',
    user_id: 'u-1',
    buyer_name: null,
    buyer_marketplace_id: 'sparrow',
    sale_price: 42.5,
    currency: 'EUR',
    shipping_cost_actual: null,
    platform_fee: 0,
    payment_processing_fee: 0,
    net_proceeds: 42.5,
    tracking_number: null,
    carrier: null,
    status: 'completed',
    sold_at: '2026-09-18T10:00:00Z',
    ...over,
  };
}

beforeEach(() => jest.clearAllMocks());

describe('listMarketplaceSales', () => {
  it('maps snake_case to the camelCase the screens read', async () => {
    mockGet.mockResolvedValue({ sales: [serverSale()] });
    const [sale] = await listMarketplaceSales();

    expect(sale.salePrice).toBe(42.5);
    expect(sale.netProceeds).toBe(42.5);
    expect(sale.listingId).toBe('l-1');
    expect(sale.soldAt).toBe('2026-09-18T10:00:00Z');
    // The bug, stated as an assertion: these were undefined, and the Revenue
    // Summary adds them up.
    expect(Number.isNaN(sale.salePrice + sale.netProceeds)).toBe(false);
  });

  it('keeps an unrecorded postage as NULL rather than zero', async () => {
    mockGet.mockResolvedValue({ sales: [serverSale()] });
    const [sale] = await listMarketplaceSales();
    // `?? 0` here would say "postage cost nothing" for every sale a completed
    // Sparrow trade records, and the dashboard decides "Net" vs "Net before
    // postage" on exactly this.
    expect(sale.shippingCostActual).toBeNull();
  });

  it('keeps a recorded postage of zero as zero', async () => {
    mockGet.mockResolvedValue({ sales: [serverSale({ shipping_cost_actual: 0 })] });
    const [sale] = await listMarketplaceSales();
    expect(sale.shippingCostActual).toBe(0);
  });

  it('reads a real recorded sale end to end', async () => {
    mockGet.mockResolvedValue({
      sales: [serverSale({
        sale_price: 1000, shipping_cost_actual: 15, platform_fee: 132.8,
        payment_processing_fee: 0.3, net_proceeds: 852.2, buyer_name: 'collector_jane',
      })],
    });
    const [sale] = await listMarketplaceSales();
    expect(sale.salePrice).toBe(1000);
    expect(sale.platformFee).toBe(132.8);
    expect(sale.shippingCostActual).toBe(15);
    expect(sale.netProceeds).toBe(852.2);
    expect(sale.buyerName).toBe('collector_jane');
  });

  it('survives a bare array and an empty answer', async () => {
    mockGet.mockResolvedValue([serverSale()]);
    expect((await listMarketplaceSales())[0].salePrice).toBe(42.5);
    mockGet.mockResolvedValue({ sales: [] });
    expect(await listMarketplaceSales()).toEqual([]);
  });
});

/**
 * The same cast bug, on the path that quotes a member their fees.
 *
 * `calculateFee` does `feeSchedules.find((s) => s.marketplaceId === mpId)`, so
 * an unmapped payload never matched and the estimate always fell back to
 * `MARKETPLACE_OPTIONS.defaultFeePct` with `estimated: true`. The honesty flag
 * was doing its job; the reason it could never turn off was this.
 */
function serverFee(over: Record<string, unknown> = {}) {
  return {
    marketplace_id: 'ebay',
    display_name: 'eBay',
    base_fee_pct: 12.9,
    payment_processing_pct: 2.9,
    fixed_fee: 0.3,
    currency: 'EUR',
    notes: null,
    ...over,
  };
}

describe('getMarketplaceFeeSchedules', () => {
  it('maps the fields calculateFee matches and multiplies on', async () => {
    mockGet.mockResolvedValue({ fee_schedules: [serverFee()] });
    const [fee] = await getMarketplaceFeeSchedules();

    // The match key — undefined here is why the server schedule was unusable.
    expect(fee.marketplaceId).toBe('ebay');
    expect(fee.baseFeePct).toBe(12.9);
    expect(fee.paymentProcessingPct).toBe(2.9);
    expect(fee.fixedFee).toBe(0.3);
    // price * undefined / 100 is NaN; the find() miss is all that hid it.
    expect(Number.isNaN(100 * fee.baseFeePct / 100)).toBe(false);
  });

  it('carries the 0% Sparrow takes on its own marketplace', async () => {
    // The client's fallback guesses 5% here. Sparrow charges nothing (P2P spec
    // §5b) — the 5% in the terms is event tickets.
    mockGet.mockResolvedValue({
      fee_schedules: [serverFee({ marketplace_id: 'collectai', display_name: 'CollectAI P2P', base_fee_pct: 0, payment_processing_pct: 0, fixed_fee: 0 })],
    });
    const [fee] = await getMarketplaceFeeSchedules();
    expect(fee.marketplaceId).toBe('collectai');
    expect(fee.baseFeePct).toBe(0);
    expect(fee.paymentProcessingPct).toBe(0);
  });
});
