/**
 * Data moat analytics, supply/demand, scarcity, and prediction accuracy API methods.
 */
import { get } from "./httpClient";

export const getSupplyTrends = (category?: string, days = 30) => {
  const sp = new URLSearchParams();
  if (category) sp.set("category", category);
  sp.set("days", String(days));
  return get<{
    trends: Array<{
      date: string;
      listing_count: number;
      avg_price: number;
      category: string;
    }>;
  }>(`/data-moat/supply-trends?${sp.toString()}`);
};

export const getDemandHeat = (category?: string) =>
  get<{
    items: Array<{
      item_key: string;
      title: string;
      category: string;
      demand_score: number;
      search_count: number;
    }>;
  }>(`/data-moat/demand-heat${category ? `?category=${encodeURIComponent(category)}` : ""}`);

export const getScarcityScores = (category?: string) =>
  get<{
    items: Array<{
      item_key: string;
      title: string;
      scarcity_score: number;
      listing_count: number;
      supply_trend: string;
    }>;
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
