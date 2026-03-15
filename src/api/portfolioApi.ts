/**
 * Portfolio analytics API methods.
 */
import { get } from "./httpClient";

export const getPortfolioOverview = () => get("/portfolio/overview");

export const getPortfolioTimeseries = (range?: string) =>
  get(`/portfolio/timeseries${range ? `?range=${encodeURIComponent(range)}` : ""}`);

export const getPortfolioCategoryBreakdown = () => get("/portfolio/category-breakdown");

export const getPortfolioCategoryStats = () => get("/portfolio/category-stats");

export const getCategoryHealth = () => get("/portfolio/category-health");

export const getCategoryCrossCorrelation = (category: string) =>
  get(`/portfolio/category-correlation?category=${encodeURIComponent(category)}`);
