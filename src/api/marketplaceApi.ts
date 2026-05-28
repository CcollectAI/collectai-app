/**
 * Marketplace search, listings, accounts, fees, sales, and affiliate API methods.
 */
import { get, post, del, patch, put, LONG_REQUEST_TIMEOUT_MS } from "./httpClient";
import { MarketplaceSearchResponseSchema, safeParse } from "./schemas";
import type { MarketplaceSearchResponse } from "./schemas";

// Marketplace search (legacy + aggregation) — live-aggregates across 44
// adapters server-side; can take 40+ s legitimately.
export const marketSearch = (query: string, opts?: {
  category_id?: string;
  subtype_id?: string;
  collections?: string[];
  limit?: number;
  sold_only?: boolean;
  min_price?: number;
  max_price?: number;
}) => post("/marketplace/search", { query, ...opts }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

export const marketplaceSearch = async (query: string, opts?: {
  category?: string;
  limit?: number;
  region?: string;
  source?: string[];
  condition?: string[];
  min_price?: number;
  max_price?: number;
  sort?: string;
}): Promise<MarketplaceSearchResponse> => {
  const raw = await post("/marketplace/search", { query, ...opts }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });
  return safeParse(MarketplaceSearchResponseSchema, raw, { results: [], hits: [] });
};

export const marketplaceComps = (itemRef: string, category?: string, region?: string) =>
  post(`/marketplace/comps/${encodeURIComponent(itemRef)}`, { category, region }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

// Affiliate links
export const getAffiliateLinks = (query: string, category?: string, limit = 6, region?: string) =>
  get<{
    links: {
      source: string;
      url: string;
      affiliate_url: string;
      label: string;
    }[];
  }>(`/marketplace/affiliate-links?query=${encodeURIComponent(query)}${category ? `&category=${encodeURIComponent(category)}` : ""}&limit=${limit}${region ? `&region=${encodeURIComponent(region)}` : ""}`);

export const tagAffiliateUrl = (url: string, source: string) =>
  post<{ url: string; affiliate_url: string; source: string }>(
    '/marketplace/affiliate-url', { url, source }
  );

// Marketplace Listings (Multi-Marketplace Selling)
export const createMarketplaceListing = (payload: {
  item_id: string;
  marketplace_id: string;
  price: number;
  currency?: string;
  format?: string;
  condition_description?: string;
}) => post("/marketplace/listings", payload as Record<string, unknown>);

export const listMarketplaceListings = (opts?: { status?: string; marketplace_id?: string; limit?: number; offset?: number }) => {
  const sp = new URLSearchParams();
  if (opts?.status) sp.set("status", opts.status);
  if (opts?.marketplace_id) sp.set("marketplace_id", opts.marketplace_id);
  if (opts?.limit) sp.set("limit", String(opts.limit));
  if (opts?.offset) sp.set("offset", String(opts.offset));
  const q = sp.toString();
  return get(`/marketplace/listings${q ? `?${q}` : ""}`);
};

export const updateMarketplaceListing = (listingId: string, payload: Record<string, unknown>) =>
  patch(`/marketplace/listings/${encodeURIComponent(listingId)}`, payload);

export const deleteMarketplaceListing = (listingId: string) =>
  del(`/marketplace/listings/${encodeURIComponent(listingId)}`);

export const publishMarketplaceListing = (listingId: string) =>
  post(`/marketplace/listings/${encodeURIComponent(listingId)}/publish`);

export const calculateMarketplaceFees = (payload: { price: number; marketplace_id: string; category?: string }) =>
  post("/marketplace/listings/fees/calculate", payload as Record<string, unknown>);

// Marketplace Listing Accounts
export const listMarketplaceAccounts = () =>
  get("/marketplace/listings/accounts");

export const connectMarketplaceAccount = (payload: { marketplace_id: string; seller_name?: string; api_key?: string }) =>
  post("/marketplace/listings/accounts", payload as Record<string, unknown>);

export const disconnectMarketplaceAccount = (accountId: string) =>
  del(`/marketplace/listings/accounts/${encodeURIComponent(accountId)}`);

export const getMarketplaceFeeSchedules = () =>
  get("/marketplace/listings/fees");

export const listMarketplaceSales = (opts?: { marketplace_id?: string; limit?: number; offset?: number }) => {
  const sp = new URLSearchParams();
  if (opts?.marketplace_id) sp.set("marketplace_id", opts.marketplace_id);
  if (opts?.limit) sp.set("limit", String(opts.limit));
  if (opts?.offset) sp.set("offset", String(opts.offset));
  const q = sp.toString();
  return get(`/marketplace/listings/sales${q ? `?${q}` : ""}`);
};

export const recordMarketplaceSale = (listingId: string, payload: { sale_price: number; buyer_name?: string }) =>
  post(`/marketplace/listings/sales/${encodeURIComponent(listingId)}/record`, payload as Record<string, unknown>);

// On-demand enrichment — fires a paid scrape for one item to get fresh
// comps. Server-side cache (TTL 14d default, 30d for slow-moving cats).
// Returns { skipped, reason, hits_persisted, cost_cents }. When the
// SCRAPEDO_ENABLED env is off on the server, returns
// reason='scrapedo_disabled' cleanly so the UI can show a graceful state.
export const enrichOnDemand = (payload: {
  item_ref: string;
  query: string;
  category: string;
}) => post("/enrich/on-demand", payload as Record<string, unknown>, { timeoutMs: LONG_REQUEST_TIMEOUT_MS });

// eBay seller-OAuth flow.
// Step 1: ask backend for the consent URL → open in browser.
// Step 2: user signs in on ebay.com, eBay redirects to our callback,
//         backend exchanges code → tokens stored in marketplace_accounts.
// Step 3: FE polls listMarketplaceAccounts() to detect the new ebay row.
export const startEbayOauth = () =>
  get("/marketplace/listings/accounts/oauth/ebay/start") as Promise<{
    redirect_url: string;
    state: string;
  }>;

// Per-account publish defaults — eBay requires categoryId + 3 policy IDs.
// Without these, /publish returns 412 with the missing-fields list.
export const getEbayDefaults = () =>
  get("/marketplace/listings/accounts/defaults/ebay");

export const setEbayDefaults = (payload: {
  ebay_category_id: string;
  fulfillment_policy_id: string;
  payment_policy_id: string;
  return_policy_id: string;
  location_key?: string;
}) => put("/marketplace/listings/accounts/defaults/ebay", payload as Record<string, unknown>);

// Seller age verification — one-time gate replacing the onboarding checkbox.
// Backend mutating /marketplace/listings/* endpoints return 412 with
// detail.error === 'seller_age_verification_required' until this fires once.
export const verifySellerAge = () =>
  post<{ seller_age_verified_at: string }>(
    "/marketplace/listings/age-verify",
    { confirmed: true } as Record<string, unknown>,
  );
