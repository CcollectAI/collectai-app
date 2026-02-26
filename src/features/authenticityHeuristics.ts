import type { CurrencyCode } from '@/data/types';

export type QuickScanPrediction = {
  name?: string;
  estimated_mid?: number;
  category?: string;
  currency?: CurrencyCode;
  confidence?: number;
  price_band?: string;
};

export type AuthenticityAssessment = {
  label: 'Likely authentic' | 'Check details' | 'High risk / uncertain';
  score: number; // 0–100
  reasons: string[];
  guidance: string;
};

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

export function assessAuthenticity(
  prediction: QuickScanPrediction | null | undefined
): AuthenticityAssessment | null {
  if (!prediction) return null;

  const confidence = clamp01(prediction.confidence ?? 0.5);
  const value = prediction.estimated_mid ?? null;
  const reasons: string[] = [];

  if (prediction.category) {
    reasons.push(`Category: ${prediction.category}`);
  }
  if (value != null) {
    const currency = prediction.currency ?? 'EUR';
    reasons.push(`Estimated value: ${value} ${currency}`);
  }
  if (prediction.price_band) {
    reasons.push(`Price band: ${prediction.price_band}`);
  }
  reasons.push(`Model confidence: ${(confidence * 100).toFixed(0)}%`);

  let score = confidence * 100;
  let label: AuthenticityAssessment['label'] = 'Check details';
  let guidance =
    'This is an automated authenticity hint based on image + model confidence. Always cross-check with your usual buying checks.';

  if (value != null && value >= 10000 && confidence < 0.65) {
    score = Math.min(score, 40);
    reasons.push(
      'High estimated value with only moderate confidence – treat offers well below this with caution.'
    );
  }

  if (confidence >= 0.9) {
    label = 'Likely authentic';
    guidance =
      'Confidence is high and price band looks reasonable for this category. Still verify seller reputation and condition before buying.';
  } else if (confidence >= 0.65) {
    label = 'Check details';
    guidance =
      'Signals look decent, but confidence is not maximal. Compare photos, check seller history, and confirm condition.';
  } else {
    label = 'High risk / uncertain';
    guidance =
      'Signals are noisy or conflicting. Treat as high-risk: buy only from trusted sellers, ask for more photos, or avoid if deal looks too good.';
  }

  return {
    label,
    score: Math.round(score),
    reasons,
    guidance,
  };
}
