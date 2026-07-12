/**
 * Data moat analytics, supply/demand, scarcity, and prediction accuracy API methods.
 */
import { get } from "./httpClient";

export const getSupplyTrends = (category?: string, days = 30) => {
  const sp = new URLSearchParams();
  if (category) sp.set("category", category);
  sp.set("days", String(days));
  return get<{
    trends: {
      date: string;
      listing_count: number;
      avg_price: number;
      category: string;
    }[];
  }>(`/data-moat/supply-trends?${sp.toString()}`);
};

export const getDemandHeat = (category?: string) =>
  get<{
    items: {
      item_key: string;
      title: string;
      category: string;
      demand_score: number;
      search_count: number;
    }[];
  }>(`/data-moat/demand-heat${category ? `?category=${encodeURIComponent(category)}` : ""}`);

export const getScarcityScores = (category?: string) =>
  get<{
    items: {
      item_key: string;
      title: string;
      scarcity_score: number;
      listing_count: number;
      supply_trend: string;
    }[];
  }>(`/data-moat/scarcity${category ? `?category=${encodeURIComponent(category)}` : ""}`);

export const getDemandHeatByRegion = (category?: string, days = 7) => {
  const sp = new URLSearchParams({ days: String(days) });
  if (category) sp.set("category", category);
  return get(`/data-moat/demand-heat/by-region?${sp.toString()}`);
};

export const getPredictionAccuracy = (category?: string, days = 30) => {
  const sp = new URLSearchParams({ days: String(days) });
  if (category) sp.set("category", category);
  return get(`/data-moat/prediction-accuracy?${sp.toString()}`);
};

// Market Movers — biggest price gainers/losers from the market_hits_daily rollup.
export type TopMover = {
  item_ref: string;
  category: string;
  item_key?: string | null;
  title?: string | null;
  brand?: string | null;
  set_code?: string | null;
  image_url?: string | null;
  last_price: number;
  med_7d?: number | null;
  med_30d?: number | null;
  delta_pct_7d?: number | null;
  delta_pct_30d?: number | null;
  comps_30d: number;
  in_catalog: boolean;
};

export type TopMoversResponse = {
  movers: TopMover[];
  direction: "gainers" | "losers";
  window: "7d" | "30d";
};

export const getTopMovers = (opts?: {
  direction?: "gainers" | "losers";
  window?: "7d" | "30d";
  categories?: string[];
  limit?: number;
}) => {
  const sp = new URLSearchParams();
  if (opts?.direction) sp.set("direction", opts.direction);
  if (opts?.window) sp.set("window", opts.window);
  if (opts?.categories?.length) sp.set("categories", opts.categories.join(","));
  if (opts?.limit) sp.set("limit", String(opts.limit));
  const qs = sp.toString();
  return get<TopMoversResponse>(`/catalog/top-movers${qs ? `?${qs}` : ""}`);
};
