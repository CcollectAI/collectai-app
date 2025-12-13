/**
 * Minimal shape of the QuickScan prediction we care about.
 * Adapt this to match your real QuickScanResult type.
 */
export interface QuickScanPrediction {
  name: string;
  estimated_mid: number | null;
  estimated_low?: number | null;
  estimated_high?: number | null;
  currency?: string | null;
  confidence?: number | null; // 0–1 if available
}

export interface AntiFraudInput {
  prediction: QuickScanPrediction | null;
  /** Optional: what the seller is asking in the real world, in same currency. */
  askingPrice?: number | null;
  /** Optional: your internal cost basis, if you already own it. */
  costBasis?: number | null;
}

export type AntiFraudRiskLevel = 'low' | 'medium' | 'high';

export interface AntiFraudResult {
  risk: AntiFraudRiskLevel;
  score: number; // 0–100
  summary: string;
  details: {
    estimatedMid?: number | null;
    askingPrice?: number | null;
    costBasis?: number | null;
    premiumPct?: number | null;
    discountPct?: number | null;
    confidence?: number | null;
  };
}

/**
 * Heuristic anti-fraud scoring:
 * - Compares askingPrice to estimated_mid.
 * - Discounts above +50% with higher risk.
 * - Incorporates model confidence if present.
 *
 * This is intentionally stateless and client-side only.
 */
export function computeAntiFraudSignal(input: AntiFraudInput): AntiFraudResult {
  const { prediction, askingPrice, costBasis } = input;

  if (!prediction || prediction.estimated_mid == null) {
    return {
      risk: 'medium',
      score: 50,
      summary:
        'Not enough model data yet — double-check seller and item provenance.',
      details: {
        estimatedMid: prediction?.estimated_mid ?? null,
        askingPrice: askingPrice ?? null,
        costBasis: costBasis ?? null,
        premiumPct: null,
        discountPct: null,
        confidence: prediction?.confidence ?? null,
      },
    };
  }

  const mid = prediction.estimated_mid;
  const price = askingPrice ?? mid;
  const diff = price - mid;
  const premiumPct = (diff / mid) * 100;
  const discountPct = premiumPct < 0 ? -premiumPct : 0;
  const confidence = prediction.confidence ?? 0.6;

  let baseRisk: AntiFraudRiskLevel = 'low';
  let score = 80;

  if (premiumPct > 100) {
    baseRisk = 'high';
    score = 20;
  } else if (premiumPct > 50) {
    baseRisk = 'high';
    score = 30;
  } else if (premiumPct > 25) {
    baseRisk = 'medium';
    score = 45;
  } else if (premiumPct < -40) {
    // Very cheap relative to model — could also be fake / damaged.
    baseRisk = 'medium';
    score = 55;
  } else {
    baseRisk = 'low';
    score = 75;
  }

  // Adjust score by confidence: less confidence → more conservative
  const confidenceFactor = confidence; // 0–1
  score = score * confidenceFactor + 50 * (1 - confidenceFactor);
  score = Math.max(0, Math.min(100, score));

  let risk: AntiFraudRiskLevel = baseRisk;
  if (score >= 70) risk = 'low';
  else if (score >= 40) risk = 'medium';
  else risk = 'high';

  let summary: string;
  if (risk === 'high') {
    summary =
      'High anti-fraud risk — price is far from model estimate or confidence is low. Slow down and verify authenticity.';
  } else if (risk === 'medium') {
    summary =
      'Medium anti-fraud risk — there are some mismatches. Do extra checks before buying.';
  } else {
    summary =
      'Low anti-fraud risk based on current model and price comparison. Still verify condition and seller reputation.';
  }

  return {
    risk,
    score,
    summary,
    details: {
      estimatedMid: mid,
      askingPrice: askingPrice ?? null,
      costBasis: costBasis ?? null,
      premiumPct,
      discountPct,
      confidence,
    },
  };
}
