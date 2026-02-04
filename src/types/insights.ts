/**
 * Portfolio Insights Types
 * Data structures for portfolio analytics and alerts.
 */

export type PortfolioInsights = {
  /** Total portfolio value in user's currency */
  totalValue: number;
  /** Value change over period */
  valueChange: number;
  /** Percentage change over period */
  percentChange: number;
  /** Period for the change calculation */
  period: '7d' | '30d' | '90d';
  /** Top gaining items */
  topGainers: ItemMover[];
  /** Top losing items */
  topLosers: ItemMover[];
  /** Watchlist summary */
  watchlistSummary: WatchlistSummary;
  /** Timestamp of last calculation */
  calculatedAt: string;
};

export type ItemMover = {
  itemId: string;
  name: string;
  category: string;
  currentValue: number;
  previousValue: number;
  absoluteChange: number;
  percentChange: number;
  imageUrl?: string;
};

export type WatchlistSummary = {
  /** Total items on watchlist */
  totalItems: number;
  /** Items below target price */
  belowTargetCount: number;
  /** Items with price drops */
  priceDropCount: number;
  /** New listings for watched items */
  newListingsCount: number;
};

export type AlertType = 'price_drop' | 'new_listing' | 'milestone' | 'price_increase';

export type Alert = {
  id: string;
  type: AlertType;
  itemId: string;
  itemName: string;
  itemCategory: string;
  itemImageUrl?: string;
  /** Human-readable description */
  description: string;
  /** The condition that triggered this alert */
  condition: string;
  /** Relevant value (e.g., new price, % change) */
  value: number;
  /** Previous value for comparison */
  previousValue?: number;
  /** When the alert was triggered */
  triggeredAt: string;
  /** Whether the user has seen this alert */
  isRead: boolean;
};

export type AlertPreferences = {
  /** Enable price drop alerts */
  priceDropEnabled: boolean;
  /** Threshold for price drop alerts (percentage) */
  priceDropThreshold: number;
  /** Enable new listing alerts */
  newListingEnabled: boolean;
  /** Enable milestone alerts */
  milestoneEnabled: boolean;
  /** Enable price increase alerts */
  priceIncreaseEnabled: boolean;
  /** Threshold for price increase alerts (percentage) */
  priceIncreaseThreshold: number;
  /** Notification frequency */
  frequency: 'immediate' | 'daily' | 'weekly';
};

export const DEFAULT_ALERT_PREFERENCES: AlertPreferences = {
  priceDropEnabled: true,
  priceDropThreshold: 10,
  newListingEnabled: true,
  milestoneEnabled: true,
  priceIncreaseEnabled: false,
  priceIncreaseThreshold: 20,
  frequency: 'daily',
};
