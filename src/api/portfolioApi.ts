/**
 * Portfolio analytics API methods.
 */
import { get } from "./httpClient";
import { PortfolioSnapshotSchema, safeParse } from "./schemas";
import type { PortfolioSnapshot } from "./schemas";

export const getPortfolioOverview = async (): Promise<PortfolioSnapshot> => {
  const raw = await get("/portfolio/overview");
  return safeParse(PortfolioSnapshotSchema, raw, { total_value: 0, item_count: 0, categories: [] });
};

export const getPortfolioTimeseries = (range?: string) =>
  get(`/portfolio/timeseries${range ? `?range=${encodeURIComponent(range)}` : ""}`);

/**
 * The user's holdings, normalised by `portfolioAnalyticsStore`.
 *
 * Added 2026-08-13. This endpoint was previously reached only through
 * `src/services/collectorsClient.ts`, a second HTTP client that sends
 * `X-API-Key` and NO `Authorization` header — so it returned 401 on every
 * request it ever made in production (bake.log: 4 requests, 4 × 401, zero
 * 200s) and the analytics portfolio snapshot has never had real data.
 */
export const getPortfolioItems = () => get("/portfolio/items");

/**
 * RAW `/portfolio/overview`, deliberately unparsed.
 *
 * `getPortfolioOverview()` above runs the response through
 * `PortfolioSnapshotSchema`, which declares no `sets` key — zod strips it, so
 * the typed getter cannot be used to read set completion. Anything needing
 * `sets` must use this one.
 */
export const getPortfolioOverviewRaw = () => get("/portfolio/overview");

// Lives under /analytics on the server (trends_and_deepdive_router has
// prefix=/analytics). Earlier path was missing the prefix and 404'd.
export const getPortfolioCategoryBreakdown = () => get("/analytics/portfolio/category-breakdown");

export const getPortfolioCategoryStats = () => get("/portfolio/category-stats");

export const getCategoryHealth = () => get("/portfolio/category-health");

export const getCategoryCrossCorrelation = (category: string) =>
  get(`/portfolio/category-correlation?category=${encodeURIComponent(category)}`);

/**
 * Realised profit and loss — what the member ACTUALLY made, after every fee on
 * both sides. `unrealized_pl` elsewhere is a projection against a live estimate;
 * this is the only figure in the app that reports a closed position.
 *
 * ⚠️ `profit` is `null`, never 0, when the sold item has no recorded purchase
 * price. There is no basis to subtract, and rendering the whole net proceeds as
 * profit is the `None or 0` failure that turns UNKNOWN into a confident number.
 * `sales_without_cost_basis` says how many rows that applies to, and
 * `total_profit` EXCLUDES them — a caller that ignores it is quoting a total
 * that quietly under-counts.
 */
export type RealisedSale = {
  id: string;
  item_id: string | null;
  item_name: string | null;
  category: string | null;
  sold_at: string | null;
  sale_price: number | null;
  currency: string | null;
  net_proceeds: number | null;
  /** All money on this row is EUR — the server converts before subtracting the
   *  EUR cost basis. This is the currency the SELLER used, kept so a member who
   *  sold in USD is not told the sale was in euros. */
  sale_currency: string | null;
  cost_basis: number | null;
  cost_basis_known: boolean;
  /** False when the seller has not said what postage cost — `profit` is then
   *  null, because a net BEFORE postage presented as a result is exactly the
   *  §5 error this feature exists to prevent. The server has always sent this;
   *  the type dropped it (class T). */
  shipping_known: boolean;
  profit: number | null;
  fees: { platform: number; payment_processing: number; shipping: number };
};

export type RealisedPL = {
  sales: RealisedSale[];
  count: number;
  total_profit: number;
  total_net_proceeds: number;
  sales_without_cost_basis: number;
  /** Sales excluded from `total_profit` because postage is unrecorded. Shown
   *  beside `sales_without_cost_basis`, never silently folded in. */
  sales_without_shipping: number;
};

export const getRealisedPL = () => get<RealisedPL>("/portfolio/realised-pl");
