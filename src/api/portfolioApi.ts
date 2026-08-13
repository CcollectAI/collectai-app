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
