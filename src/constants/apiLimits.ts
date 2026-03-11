/**
 * Centralized pagination and query limit constants.
 * Replaces magic numbers scattered across data providers and hooks.
 */

export const API_LIMITS = {
  PORTFOLIO_VALUES_DAYS: 365,
  ITEMS_DEFAULT: 200,
  RECENT_ITEMS: 25,
  ACTIVITY_FEED: 20,
  ALERTS_DEFAULT: 50,
  BATCH_PROJECTS: 500,
  BATCH_LARGE: 2000,
} as const;
