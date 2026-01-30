/**
 * Shared types for DataProvider abstraction.
 * These are the stable shapes returned to UI — no raw Supabase responses.
 */

export type PortfolioSummary = {
  total: number;
  deltaPct: number;
  itemCount: number;
};

export type Item = {
  id: string;
  name: string;
  category: string;
  price: number;
  imageUrl?: string;
  updatedAt?: string;
};

export type WatchlistItem = {
  id: string;
  title: string;
  priority: 'high' | 'medium' | 'low';
  owned: boolean;
  targetPrice: number | null;
  currency: string;
};

export type CreateItemInput = {
  name: string;
  category: string;
  price: number;
  imageUrl?: string;
};

/**
 * QuickScan types — matches backend /quickscan-advanced/single response.
 */
export type QuickScanAttributes = {
  category: string;
  editionGuess?: string | null;
  conditionGuess?: string | null;
  rarityScore?: number | null;
};

export type QuickScanPrediction = {
  name: string;
  estimatedLow: number;
  estimatedMid: number;
  estimatedHigh: number;
  currency: string;
  confidence: number;
};

export type QuickScanResult = {
  itemId?: string | null;
  attributes: QuickScanAttributes;
  prediction: QuickScanPrediction;
};
