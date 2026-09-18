/**
 * Deals domain provider — external marketplace listings, accounts and sales.
 *
 * The Deal Desk offer functions (propose/counter/respond/cancel/ship/complete/
 * active/history/detail/reputation) were removed 2026-08-09 with the rest of
 * that subsystem, and `toggleForSale` followed on 2026-09-08: its route
 * (`PUT /items/*​/for-sale`) had already been deleted server-side, and
 * `items.for_sale` is owned by the `trg_sync_item_for_sale` trigger on
 * `marketplace_listings` — a direct write would be overwritten by the trigger
 * on the next listing change.
 *
 * What remains drives the external marketplace-connections feature.
 * Member-to-member selling lives in `src/api/p2pApi.ts`.
 */

import type {
  MarketplaceListing,
  MarketplaceAccount,
  MarketplaceSale,
  MarketplaceFeeSchedule,
} from '../types';
import { collectorsApi } from '../../api/collectorsApi';












// Multi-Marketplace Selling
/**
 * These two endpoints return an ENVELOPE, not a bare array:
 *   GET /marketplace/listings       -> { listings: [...], total_count }
 *   GET /marketplace/listings/sales -> { sales: [...],    total_count }
 * while /accounts and /fees return bare arrays. The signatures here promised
 * arrays for all four, so the Seller Dashboard got an object, and
 * `for (const s of sales)` threw `TypeError: iterator method is not callable`
 * — the whole screen fell into its ScreenErrorBoundary ("Seller Dashboard
 * failed to load"). `?? []` did not save it: an object is truthy.
 * Verified against prod 2026-08-01 with a real user token.
 */
function unwrap<T>(res: unknown, key: string): T[] {
  if (Array.isArray(res)) return res as T[];
  const inner = (res as Record<string, unknown> | null)?.[key];
  return Array.isArray(inner) ? (inner as T[]) : [];
}

/** `ListingResponse` (marketplace_listing_router.py) — snake_case. */
type RawListing = Record<string, unknown>;

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);
const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);

/**
 * MAPPED, not cast (2026-09-18) — and this one was visible.
 *
 * `unwrap<MarketplaceListing>(...)` asserted the server's snake_case payload to
 * be the camelCase type, so on the Sell dashboard's Listings tab
 * `listing.listingTitle` was `undefined` (blank row title, blank in the
 * accessibility label and in the "Remove ... from marketplace?" confirm), and
 * `listing.marketplaceId` was too — `MARKETPLACE_CONFIG[undefined] ??
 * MARKETPLACE_CONFIG.collectai` then badged EVERY listing as Sparrow P2P,
 * whichever marketplace it was on.
 *
 * `price`, `currency`, `status` and `quantity` happen to be spelled the same on
 * both sides, which is why the screen looked broadly right and only the names
 * and badges were wrong — the hardest kind of wrong to notice.
 */
export async function listMarketplaceListings(status?: MarketplaceListing['status']): Promise<MarketplaceListing[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  const raw = unwrap<RawListing>(await collectorsApi.get(`/marketplace/listings${qs}`), 'listings');
  return raw.map((r) => ({
    id: String(r.id),
    itemId: String(r.item_id ?? ''),
    accountId: str(r.account_id),
    marketplaceId: r.marketplace_id as MarketplaceListing['marketplaceId'],
    externalListingId: str(r.external_listing_id),
    listingUrl: str(r.listing_url),
    listingTitle: str(r.listing_title) ?? '',
    listingDescription: str(r.listing_description),
    price: num(r.price) ?? 0,
    currency: r.currency as MarketplaceListing['currency'],
    originalPrice: num(r.original_price),
    format: r.format as MarketplaceListing['format'],
    quantity: num(r.quantity) ?? 1,
    conditionLabel: str(r.condition_label),
    conditionNotes: str(r.condition_notes),
    shippingMethod: str(r.shipping_method),
    shippingCost: num(r.shipping_cost),
    shipsInternational: r.ships_international === true,
    returnsAccepted: r.returns_accepted === true,
    status: r.status as MarketplaceListing['status'],
    statusMessage: str(r.status_message),
    viewsCount: num(r.views_count) ?? 0,
    watchersCount: num(r.watchers_count) ?? 0,
    offersCount: num(r.offers_count) ?? 0,
    estimatedFees: num(r.estimated_fees),
    estimatedNet: num(r.estimated_net),
    feePercentage: num(r.fee_percentage),
    listedAt: str(r.listed_at),
    expiresAt: str(r.expires_at),
    soldAt: str(r.sold_at),
    syncedAt: str(r.synced_at),
    createdAt: str(r.created_at) ?? '',
  }));
}

export async function createMarketplaceListing(input: Omit<MarketplaceListing, 'id' | 'viewsCount' | 'watchersCount' | 'offersCount' | 'createdAt'>): Promise<MarketplaceListing> {
  return collectorsApi.post('/marketplace/listings', input as Record<string, unknown>);
}

export async function updateMarketplaceListing(listingId: string, patch: Partial<MarketplaceListing>): Promise<MarketplaceListing> {
  return collectorsApi.patch(`/marketplace/listings/${listingId}`, patch as Record<string, unknown>);
}

export async function deleteMarketplaceListing(listingId: string): Promise<void> {
  await collectorsApi.delete(`/marketplace/listings/${listingId}`);
}

/**
 * Same cast, same fix (2026-09-18): the Accounts tab read `account.marketplaceId`
 * off a payload that spells it `marketplace_id`, so every connected account
 * rendered as Sparrow P2P and "Disconnect Account?" named the wrong one.
 */
export async function listMarketplaceAccounts(): Promise<MarketplaceAccount[]> {
  // Bare array today, but unwrap defensively so an envelope added later cannot
  // reintroduce the crash above.
  const raw = unwrap<Record<string, unknown>>(
    await collectorsApi.get('/marketplace/listings/accounts'),
    'accounts',
  );
  return raw.map((r) => ({
    id: String(r.id),
    marketplaceId: r.marketplace_id as MarketplaceAccount['marketplaceId'],
    sellerName: str(r.seller_name),
    sellerId: str(r.seller_id),
    isActive: r.is_active !== false,
    connectedAt: str(r.connected_at) ?? '',
    lastSyncAt: str(r.last_sync_at),
  }));
}

/** The server answers in snake_case; `MarketplaceSale` is camelCase. */
type RawSale = {
  id: string;
  listing_id: string;
  buyer_name?: string | null;
  sale_price: number;
  currency: string;
  shipping_cost_actual?: number | null;
  platform_fee?: number | null;
  payment_processing_fee?: number | null;
  net_proceeds: number;
  tracking_number?: string | null;
  carrier?: string | null;
  status: MarketplaceSale['status'];
  sold_at: string;
};

/**
 * MAPPED, not cast (2026-09-18).
 *
 * This was `unwrap<MarketplaceSale>(...)` — a cast of the server's snake_case
 * payload to a camelCase type, so at runtime every `salePrice` and
 * `netProceeds` was `undefined`. The Sales tab's Revenue Summary sums them, so
 * it would have rendered `NaN` for gross and net.
 *
 * Nobody had seen it because `marketplace_sales` held **0 rows** for the life
 * of the marketplace — nothing wrote one until completion started recording the
 * sale, which is what turned this from dormant to about-to-ship. A cast is not
 * a mapping, and TypeScript cannot tell you so: `unwrap<T>` asserts the shape
 * rather than checking it.
 */
export async function listMarketplaceSales(): Promise<MarketplaceSale[]> {
  const raw = unwrap<RawSale>(await collectorsApi.get('/marketplace/listings/sales'), 'sales');
  return raw.map((r) => ({
    // No `Number()` and no `parseMoney()`: these arrive as JSON NUMBERS from
    // FastAPI (`SaleResponse.sale_price: float`), not as anything a member
    // typed. `parseMoney` is for member input — "12,50" — and `Number()` on a
    // value that is already a number is noise that reads like a money parse.
    // `npm run check:numbers` flagged the wrapper, correctly, on that reading.
    id: String(r.id),
    listingId: String(r.listing_id),
    buyerName: r.buyer_name ?? null,
    salePrice: r.sale_price,
    currency: r.currency as MarketplaceSale['currency'],
    // NULL means the postage is UNKNOWN, not zero — a sale recorded when a
    // Sparrow trade completes cannot know what the seller paid to post it, and
    // the column defaults to 0 so only null can say so. `?? null` keeps that
    // distinction; `?? 0` would erase it.
    shippingCostActual: r.shipping_cost_actual ?? null,
    platformFee: r.platform_fee ?? null,
    paymentProcessingFee: r.payment_processing_fee ?? null,
    netProceeds: r.net_proceeds,
    trackingNumber: r.tracking_number ?? null,
    carrier: r.carrier ?? null,
    status: r.status,
    soldAt: r.sold_at,
  }));
}

/** `FeeScheduleResponse` (marketplace_listing_router.py) — snake_case. */
type RawFeeSchedule = {
  marketplace_id: string;
  display_name: string;
  base_fee_pct: number;
  payment_processing_pct: number;
  fixed_fee: number;
  currency?: string;
  notes?: string | null;
};

/**
 * MAPPED, not cast (2026-09-18) — and this one was costing members money.
 *
 * Same bug as `listMarketplaceSales` above: the server answers snake_case and
 * `MarketplaceFeeSchedule` is camelCase, so `s.marketplaceId` was `undefined`
 * for every row. `useListForSale.calculateFee` does
 * `feeSchedules.find((s) => s.marketplaceId === mpId)`, which therefore NEVER
 * matched — so the fee estimate always fell through to
 * `MARKETPLACE_OPTIONS.defaultFeePct`, the client's own guess, and
 * `estimated: true` was stuck on permanently.
 *
 * That flag was added on 2026-09-17 (class sweep D) to be honest that the
 * numbers were assumed. It was doing its job; nobody found the reason it could
 * never turn off.
 *
 * What the real schedules change, read off production 2026-09-18:
 *
 * | marketplace | client guess | server |
 * |---|---|---|
 * | **Sparrow P2P** | **5.0%** | **0%** — Sparrow charges nothing on the marketplace (P2P spec §5b); the 5% in the terms is EVENT TICKETS |
 * | eBay | 12.9% | 12.9% + 2.9% processing + EUR 0.30 |
 * | StockX | 9.5% | 9.5% + 3.0% |
 * | Mercari / Cardmarket / BrickLink | 10 / 5 / 3% | the same |
 *
 * So the app was quoting a 5% fee on its OWN marketplace, which takes none, and
 * under-quoting eBay and StockX by leaving out the processing fee.
 */
export async function getMarketplaceFeeSchedules(): Promise<MarketplaceFeeSchedule[]> {
  const raw = unwrap<RawFeeSchedule>(
    await collectorsApi.get('/marketplace/listings/fees'),
    'fee_schedules',
  );
  return raw.map((r) => ({
    marketplaceId: r.marketplace_id as MarketplaceFeeSchedule['marketplaceId'],
    displayName: r.display_name,
    baseFeePct: r.base_fee_pct,
    paymentProcessingPct: r.payment_processing_pct,
    fixedFee: r.fixed_fee,
    currency: r.currency ?? 'EUR',
    notes: r.notes ?? null,
  }));
}
