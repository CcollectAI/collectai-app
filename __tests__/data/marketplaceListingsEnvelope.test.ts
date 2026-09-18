/**
 * Seller Dashboard envelope contract.
 *
 * `GET /marketplace/listings` and `/marketplace/listings/sales` return an
 * ENVELOPE — `{ listings: [...], total_count }` and `{ sales: [...],
 * total_count }` — while `/accounts` and `/fees` return bare arrays. The
 * provider signatures promised `Promise<T[]>` for all four, so the dashboard
 * received an object where it expected an array and
 * `for (const s of sales)` threw:
 *
 *     TypeError: iterator method is not callable
 *
 * The whole screen fell into its ScreenErrorBoundary and rendered
 * "Seller Dashboard failed to load" — on BOTH platforms, since nothing here is
 * Android-specific. `dashboardData?.sales ?? []` did not save it, because an
 * object is truthy; only comparing the VALUE's shape finds this.
 *
 * Shapes verified against production 2026-08-01 with a real user token.
 *
 * These tests fail against the pre-fix provider (which returned the raw
 * response) and pass after it unwraps.
 *
 * Updated 2026-09-18: two of them also asserted that the rows came back
 * UNCHANGED, which stopped being true when class U replaced the four casts
 * with real mappings. A snake_case row cast to a camelCase type type-checks and
 * is `undefined` at runtime, so "passes through untouched" was pinning the
 * defect. They now assert the mapping.
 */

const mockGet = jest.fn();

jest.mock('@/api/collectorsApi', () => ({
  collectorsApi: {
    get: (...args: unknown[]) => mockGet(...args),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

import {
  listMarketplaceListings,
  listMarketplaceSales,
  listMarketplaceAccounts,
  getMarketplaceFeeSchedules,
} from '@/data/providers/dealsProvider';

beforeEach(() => mockGet.mockReset());

describe('marketplace provider unwraps the API envelope', () => {
  it('listMarketplaceListings returns the inner array, not the envelope', async () => {
    mockGet.mockResolvedValue({ listings: [{ id: 'l1' }, { id: 'l2' }], total_count: 2 });
    const res = await listMarketplaceListings();
    expect(Array.isArray(res)).toBe(true);
    expect(res).toHaveLength(2);
    // The actual crash: iterating the un-unwrapped envelope.
    expect(() => { for (const _ of res) { /* must not throw */ } }).not.toThrow();
  });

  it('listMarketplaceSales unwraps AND maps snake_case to the camelCase type', async () => {
    // Rewritten 2026-09-18. It asserted `toEqual([{ id: 's1' }])` — the raw row
    // handed straight back. That passed only while the provider CAST the
    // payload instead of mapping it, which is class U: every camelCase field
    // was `undefined` at runtime and `tsc` could not see it. Asserting the
    // passthrough was pinning that bug, so the test went red when it was fixed.
    mockGet.mockResolvedValue({
      sales: [{
        id: 's1', listing_id: 'l9', buyer_name: 'Ash', sale_price: 42.5,
        currency: 'EUR', shipping_cost_actual: null, platform_fee: 1.2,
        payment_processing_fee: 0.5, net_proceeds: 40.8,
        tracking_number: null, carrier: null, sold_at: '2026-09-01', status: 'completed',
      }],
      total_count: 1,
    });
    const [sale] = await listMarketplaceSales();
    expect(sale.listingId).toBe('l9');
    expect(sale.salePrice).toBe(42.5);
    expect(sale.netProceeds).toBe(40.8);
    expect(sale.buyerName).toBe('Ash');
    // NULL postage means UNKNOWN, not zero — the column defaults to 0, so only
    // null can say "a Sparrow trade completed and nobody told us the postage".
    expect(sale.shippingCostActual).toBeNull();
  });

  it('maps bare-array endpoints too (accounts, fees)', async () => {
    // Was 'passes bare arrays through untouched'. "Untouched" was the bug:
    // `/accounts` and `/fees` are bare arrays, but their rows are still
    // snake_case and the types are camelCase. The fee one cost money —
    // `useListForSale.calculateFee` matches on `marketplaceId`, which was
    // always `undefined`, so every fee estimate fell back to the client's own
    // guess and `estimated: true` could never turn off.
    mockGet.mockResolvedValue([{ id: 'a1', marketplace_id: 'ebay', seller_name: 'Merle', is_active: true }]);
    const [account] = await listMarketplaceAccounts();
    expect(account.id).toBe('a1');
    expect(account.marketplaceId).toBe('ebay');
    expect(account.sellerName).toBe('Merle');

    mockGet.mockResolvedValue([{ marketplace_id: 'ebay', display_name: 'eBay', base_fee_pct: 12.9 }]);
    const [fee] = await getMarketplaceFeeSchedules();
    expect(fee.marketplaceId).toBe('ebay');
    expect(fee.baseFeePct).toBe(12.9);
    expect(fee.currency).toBe('EUR'); // defaulted, not undefined
  });

  it('never yields a non-iterable, whatever the API returns', async () => {
    for (const weird of [null, undefined, {}, { total_count: 0 }, 42, 'nope']) {
      mockGet.mockResolvedValue(weird);
      const res = await listMarketplaceSales();
      expect(Array.isArray(res)).toBe(true);
      expect(() => { for (const _ of res) { /* no throw */ } }).not.toThrow();
    }
  });
});
