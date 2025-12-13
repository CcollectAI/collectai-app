/**
 * Anti-Fraud Engine (Client-Side Scoring Core)
 *
 * This module is deliberately network-agnostic:
 * - Takes raw signals from vision, metadata, market comps, and user history.
 * - Produces a normalized risk band + breakdown in [0,1].
 *
 * Wiring to FastAPI (/vision/predict, /portfolio/scan_and_add, provenance endpoints, etc.)
 * should happen in a separate service module so this engine stays pure and testable.
 */

export type RiskBand = 'low' | 'medium' | 'high' | 'critical';

export interface VisionDuplicateSignal {
  /** FAISS or embedding distance to nearest neighbor (smaller = closer). */
  nearestDistance: number;
  /** How many near-duplicates within a tight radius. */
  duplicateCount: number;
}

export interface MetaConsistencySignal {
  /** True when category detected by vision disagrees with user-selected category. */
  categoryMismatch: boolean;
  /**
   * Title similarity in [0,1] between claimed title and canonical title
   * (e.g. based on cosine similarity).
   */
  titleSimilarity: number;
  /**
   * Attributes conflict score in [0,1]; higher means more conflicting attributes
   * (e.g. wrong set symbol, print run, serial, etc.).
   */
  attributesConflictScore: number;
}

export interface MarketAnomalySignal {
  /**
   * Z-score of price relative to trusted comps (completed listings, reference prices).
   * E.g. +3 = 3 SD above typical.
   */
  priceZScore: number;
  /**
   * Z-score of velocity (how fast listings close) relative to typical.
   * High absolute values with price anomalies can be suspicious.
   */
  velocityZScore: number;
}

export interface UserHistorySignal {
  /** Ratio of chargebacks / disputes over last N transactions, [0,1+]. */
  chargebackRate: number;
  /** Ratio of suspected fraud flags in internal systems, [0,1+]. */
  fraudFlagRate: number;
  /** Age of account in days. */
  accountAgeDays: number;
  /** Number of successfully resolved trades. */
  completedTrades: number;
}

export interface ManualFlag {
  code: string;
  message: string;
  weight?: number;
}

export interface AntiFraudContext {
  vision?: VisionDuplicateSignal;
  meta?: MetaConsistencySignal;
  market?: MarketAnomalySignal;
  user?: UserHistorySignal;
  manualFlags?: ManualFlag[];
}

export interface AntiFraudBreakdown {
  visionRisk: number;
  metaRisk: number;
  marketRisk: number;
  userRisk: number;
  manualRisk: number;
}

export interface AntiFraudAssessment {
  /** Aggregate risk score in [0,1]; higher = more suspicious. */
  score: number;
  band: RiskBand;
  breakdown: AntiFraudBreakdown;
  flags: ManualFlag[];
}

/** Internal helpers */

const EPSILON = 1e-9;

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

function logistic(x: number): number {
  // Simple smooth squashing function for z-scores
  return 1 / (1 + Math.exp(-x));
}

/**
 * Vision-based risk:
 * - Many near-duplicates of the same image may indicate copied stock photos.
 * - Very small embedding distance to a known counterfeit cluster can be suspicious.
 */
function scoreVision(signal?: VisionDuplicateSignal): number {
  if (!signal) return 0;

  const { nearestDistance, duplicateCount } = signal;

  // Low distance -> suspicious. Map distance roughly [0, 1] to [1, 0]
  const distanceComponent = clamp(1 - nearestDistance, 0, 1);

  // Duplicate count: up to 10+ counts as highly suspicious
  const dupComponent = clamp(duplicateCount / 10, 0, 1);

  // Vision risk is combination of distance and duplicates
  const risk = 0.6 * distanceComponent + 0.4 * dupComponent;
  return clamp(risk, 0, 1);
}

/**
 * Metadata consistency risk:
 * - Category mismatch is a strong signal.
 * - Low title similarity is suspicious.
 * - Attribute conflicts (wrong set, wrong rarity, etc.) are suspicious.
 */
function scoreMeta(signal?: MetaConsistencySignal): number {
  if (!signal) return 0;

  const mismatchComponent = signal.categoryMismatch ? 1 : 0;
  const titleComponent = 1 - clamp(signal.titleSimilarity, 0, 1);
  const attrComponent = clamp(signal.attributesConflictScore, 0, 1);

  const risk =
    0.5 * mismatchComponent +
    0.3 * titleComponent +
    0.2 * attrComponent;

  return clamp(risk, 0, 1);
}

/**
 * Market anomaly risk:
 * - Very underpriced items relative to comps can indicate scams.
 * - Very overpriced with abnormal velocity can indicate wash trading or spoofing.
 */
function scoreMarket(signal?: MarketAnomalySignal): number {
  if (!signal) return 0;

  const { priceZScore, velocityZScore } = signal;

  // Extreme |z| -> high risk, use logistic to convert to [0,1]
  const priceComponent = logistic(Math.abs(priceZScore) - 1); // start ramping at |z|>1
  const velocityComponent = logistic(Math.abs(velocityZScore) - 1);

  const risk = 0.7 * priceComponent + 0.3 * velocityComponent;
  return clamp(risk, 0, 1);
}

/**
 * User history risk:
 * - High chargeback / fraud flag rates are bad.
 * - Very young accounts with no track record are riskier.
 */
function scoreUser(signal?: UserHistorySignal): number {
  if (!signal) return 0;

  const chargebackComponent = clamp(signal.chargebackRate, 0, 1);
  const fraudFlagComponent = clamp(signal.fraudFlagRate, 0, 1);

  // Age: <30d = risky, 30-365d = medium, >365d = safer
  const ageDays = Math.max(0, signal.accountAgeDays);
  let ageComponent = 1;
  if (ageDays > 365) {
    ageComponent = 0.1;
  } else if (ageDays > 90) {
    ageComponent = 0.3;
  } else if (ageDays > 30) {
    ageComponent = 0.5;
  } else {
    ageComponent = 0.9;
  }

  // Completed trades help lower risk
  const completed = Math.max(0, signal.completedTrades);
  const trackRecordComponent = completed > 50 ? 0.1 : completed > 10 ? 0.3 : 0.6;

  const risk =
    0.4 * chargebackComponent +
    0.3 * fraudFlagComponent +
    0.2 * ageComponent +
    0.1 * trackRecordComponent;

  return clamp(risk, 0, 1);
}

/**
 * Manual flags risk:
 * - Each flag can carry a weight, default 0.2.
 * - Capped to 1.
 */
function scoreManual(flags?: ManualFlag[]): number {
  if (!flags || !flags.length) return 0;

  let sum = 0;
  for (const f of flags) {
    const w = typeof f.weight === 'number' ? f.weight : 0.2;
    sum += w;
  }

  return clamp(sum, 0, 1);
}

/**
 * Convert numeric risk into band.
 */
export function riskBandFromScore(score: number): RiskBand {
  if (score >= 0.8) return 'critical';
  if (score >= 0.55) return 'high';
  if (score >= 0.3) return 'medium';
  return 'low';
}

/**
 * Main entry point: given a structured context, compute risk band and breakdown.
 */
export function assessAntiFraud(context: AntiFraudContext): AntiFraudAssessment {
  const visionRisk = scoreVision(context.vision);
  const metaRisk = scoreMeta(context.meta);
  const marketRisk = scoreMarket(context.market);
  const userRisk = scoreUser(context.user);
  const manualRisk = scoreManual(context.manualFlags);

  // Weighted aggregation across pillars
  const score = clamp(
    0.3 * visionRisk +
      0.25 * metaRisk +
      0.2 * marketRisk +
      0.15 * userRisk +
      0.1 * manualRisk,
    0,
    1,
  );

  const band = riskBandFromScore(score);

  return {
    score,
    band,
    breakdown: {
      visionRisk,
      metaRisk,
      marketRisk,
      userRisk,
      manualRisk,
    },
    flags: context.manualFlags ?? [],
  };
}

/**
 * Helper: reduce item-level fraud scores into a portfolio-level signal in [0,1].
 */
export function aggregatePortfolioFraudScore(
  itemFraudScores: Array<number | undefined>,
): number {
  const scores = itemFraudScores
    .filter((s): s is number => typeof s === 'number')
    .map((s) => clamp(s, 0, 1));

  if (!scores.length) return 0;

  // Amplify tail risk (few very suspicious items) using 80/20 weighting.
  const sorted = [...scores].sort((a, b) => b - a);
  const topK = sorted.slice(0, Math.max(1, Math.round(sorted.length * 0.2)));
  const rest = sorted.slice(topK.length);

  const topAvg =
    topK.reduce((sum, v) => sum + v, 0) / Math.max(1, topK.length);
  const restAvg =
    rest.length > 0
      ? rest.reduce((sum, v) => sum + v, 0) / rest.length
      : 0;

  const aggregate = 0.7 * topAvg + 0.3 * restAvg;
  return clamp(aggregate, 0, 1);
}
