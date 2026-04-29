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

// Lives under /analytics on the server (trends_and_deepdive_router has
// prefix=/analytics). Earlier path was missing the prefix and 404'd.
export const getPortfolioCategoryBreakdown = () => get("/analytics/portfolio/category-breakdown");

export const getPortfolioCategoryStats = () => get("/portfolio/category-stats");

export const getCategoryHealth = () => get("/portfolio/category-health");

export const getCategoryCrossCorrelation = (category: string) =>
  get(`/portfolio/category-correlation?category=${encodeURIComponent(category)}`);
