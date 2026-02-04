/**
 * Price Explanation Types
 * Structured data for explainable AI pricing interfaces.
 */

export type ConfidenceTier = 'high' | 'good' | 'medium' | 'low' | 'very_low';

export type PriceBand = {
  /** 10th percentile (low estimate) */
  q10: number;
  /** 50th percentile (median estimate) */
  q50: number;
  /** 90th percentile (high estimate) */
  q90: number;
};

export type CompSource = {
  /** Source name (e.g., "eBay", "TCGPlayer") */
  source: string;
  /** Number of comparable sales used */
  count: number;
  /** Average price from this source */
  avgPrice: number;
  /** Date range of comps */
  dateRange?: string;
};

export type PriceExplanation = {
  /** Brief summary of the valuation */
  summary: string;
  /** Key factors that influenced the price */
  keyFactors: string[];
  /** Comparable sales sources used */
  compSources: CompSource[];
  /** Confidence tier */
  confidenceTier: ConfidenceTier;
  /** Confidence percentage (0-100) */
  confidencePercent: number;
  /** Standard disclaimer */
  disclaimer: string;
  /** When the estimate was calculated */
  calculatedAt: string;
};

export type PriceEstimate = {
  /** Price band with q10/q50/q90 */
  priceBand: PriceBand;
  /** Currency code */
  currency: string;
  /** Confidence tier */
  confidenceTier: ConfidenceTier;
  /** Confidence percentage (0-100) */
  confidencePercent: number;
  /** Optional explanation (loaded on demand) */
  explanation?: PriceExplanation;
};

/**
 * Get confidence tier from percentage
 */
export function getConfidenceTier(percent: number): ConfidenceTier {
  if (percent >= 80) return 'high';
  if (percent >= 60) return 'good';
  if (percent >= 40) return 'medium';
  if (percent >= 20) return 'low';
  return 'very_low';
}

/**
 * Get display label for confidence tier
 */
export function getConfidenceLabel(tier: ConfidenceTier): string {
  switch (tier) {
    case 'high': return 'High Confidence';
    case 'good': return 'Good Confidence';
    case 'medium': return 'Medium Confidence';
    case 'low': return 'Low Confidence';
    case 'very_low': return 'Very Low Confidence';
  }
}

/**
 * Get color for confidence tier
 */
export function getConfidenceColor(tier: ConfidenceTier): string {
  switch (tier) {
    case 'high': return '#22c55e';
    case 'good': return '#84cc16';
    case 'medium': return '#eab308';
    case 'low': return '#f97316';
    case 'very_low': return '#ef4444';
  }
}

/**
 * Default disclaimer text
 */
export const DEFAULT_DISCLAIMER =
  'This estimate is based on recent market data and comparable sales. ' +
  'Actual prices may vary based on condition, timing, and market conditions. ' +
  'This is not financial advice.';
