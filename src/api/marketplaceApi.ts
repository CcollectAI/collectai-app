/**
 * Marketplace search, listings, accounts, fees, sales, and affiliate API methods.
 */
import { get, post, del, patch } from "./httpClient";

// Marketplace search (legacy + aggregation)
export const marketSearch = (query: string, opts?: {
  category_id?: string;
  subtype_id?: string;
  collections?: string[];
  limit?: number;
  sold_only?: boolean;
  min_price?: number;
  max_price?: number;
}) => post("/marketplace/search", { query, ...opts });

export const marketplaceSearch = (query: string, opts?: {
  category?: string;
  limit?: number;
  region?: string;
  source?: string[];
  condition?: string[];
  min_price?: number;
  max_price?: number;
  sort?: string;
}) =>
  post("/marketplace/search", { query, ...opts });

export const marketplaceComps = (itemRef: string, category?: string, region?: string) =>
  post(`/marketplace/comps/${encodeURIComponent(itemRef)}`, { category, region });

// Affiliate links
export const getAffiliateLinks = (query: string, category?: string, limit = 6, region?: string) =>
  get<{
    links: Array<{
      source: string;
      url: string;
      affiliate_url: string;
      label: string;
    }>;
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
