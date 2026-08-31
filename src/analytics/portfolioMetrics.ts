/**
 * Collector Portfolio Analytics Engine
 *
 * Pure, deterministic analytics for treating a collectibles portfolio like an investment account:
 * - P/L over time
 * - Max drawdown
 * - Category allocations & diversification
 * - Winners / losers
 * - Completeness & rarity-based tiering
 *
 * No React / no network calls. This is reused by the store layer.
 */

export type Tier = 'Diamond' | 'Gold' | 'Silver' | 'Unranked';

export interface TimeSeriesPoint {
  /** ISO timestamp (e.g. "2025-11-20T10:00:00Z") */
  t: string;
  /** Portfolio value at time t (in base currency, e.g. EUR) */
  v: number;
}

export interface CategoryAllocation {
  category: string;
  totalValue: number;
  /** Weight in [0,1] */
  weight: number;
}

export interface PortfolioItemSnapshot {
  /** False => `unrealizedPL` is model drift rather than profit: the server used
   *  the earliest prediction as cost basis for want of a purchase price. Never
   *  sum P/L across items without checking this. */
  hasPurchasePrice?: boolean;
  /** Which link of the value chain produced `currentValue` —
   *  `catalog_daily` | `quick_scan` | `catalog_model` are comp/model-backed;
   *  `user_estimate` | `app_estimate` are numbers nobody checked; `none` means
   *  nothing answered and the value is 0.
   *
   *  Analytics splits its totals on this: calling a member's own typed figure
   *  "market value" is the thing `value_source` exists to stop. Undefined on
   *  demo rows and on any caller predating 2026-08-19 — treat as unknown, not
   *  as market. */
  valueSource?: string;
  /** 'US' | 'EU' | 'mixed'; undefined = could not tell, NOT domestic. */
  market?: string;
  id: string;
  name: string;
  category: string;
  collection?: string;
  quantity: number;

  /** Current mark-to-market value per item * quantity */
  currentValue: number;

  /** Optional cost basis; used to compute true P/L when present */
  costBasis?: number;

  /** Per-item estimated value where currentValue is unavailable */
  estimatedValue?: number;

  /** Realized profit/loss already taken (sold, traded, etc.) */
  realizedPL?: number;

  /** Unrealized mark-to-market P/L on remaining position */
  unrealizedPL?: number;

  /** Valuation band around `currentValue`. Undefined when the model produced
   *  none — treat 0 as "no band", never as a EUR 0 bound. */
  q10?: number;
  q90?: number;

  /** 1D percentage change in value, e.g. 0.05 = +5% */
  change1dPct?: number;

  /** 7D percentage change in value, e.g. -0.10 = -10% */
  change7dPct?: number;

  /** Liquidity / marketability score in [0,1] */
  liquidityScore?: number;

  /** Rarity score in [0,1] (low supply, high desirability) */
  rarityScore?: number;

  /** Set completeness contribution in [0,1] per item */
  completenessScore?: number;

  /** Fraud risk score in [0,1]; higher means riskier */
  fraudRiskScore?: number;
}

export interface SetCompletion {
  setId: string;
  setName: string;
  ownedCount: number;
  totalCount: number;
}

export interface PortfolioPLSummary {
  startValue: number;
  currentValue: number;
  deltaAbs: number;
  /** Relative P/L vs start value; e.g. 0.25 = +25% */
  deltaPct: number;
  /** Maximum drawdown from peak value (negative number; -0.30 = -30%) */
  maxDrawdownPct: number;
  /**
   * False when the series starts at zero — i.e. the member acquired everything
   * inside the window, so there is nothing to measure performance AGAINST.
   * Callers must not present `deltaAbs`/`deltaPct` as a gain when this is
   * false; there is no gain, only an acquisition.
   */
  hasBaseline: boolean;
}

export interface WinnersLosersBucket {
  winners: PortfolioItemSnapshot[];
  losers: PortfolioItemSnapshot[];
  neutral: PortfolioItemSnapshot[];
}

export interface PortfolioTierSummary {
  tier: Tier;
  rarityScore: number;
  completenessScore: number;
  diversificationScore: number;
}

export interface PortfolioSnapshot {
  pl: PortfolioPLSummary;
  series: TimeSeriesPoint[];
  allocations: CategoryAllocation[];
  winnersLosers: WinnersLosersBucket;
  tierSummary: PortfolioTierSummary;
  items: PortfolioItemSnapshot[];
}

const EPSILON = 1e-9;

/** Safe clamp helper. */
function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Compute basic P/L metrics and max drawdown from a portfolio timeseries.
 */
export function computePLFromSeries(series: TimeSeriesPoint[]): PortfolioPLSummary {
  if (!series.length) {
    return {
      startValue: 0,
      currentValue: 0,
      deltaAbs: 0,
      deltaPct: 0,
      maxDrawdownPct: 0,
      hasBaseline: false,
    };
  }

  const sorted = [...series].sort(
    (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime(),
  );

  const startValue = sorted[0].v;
  const currentValue = sorted[sorted.length - 1].v;

  /**
   * A portfolio whose series STARTS at zero has no baseline to measure against.
   * That is the normal state for anyone who added their items inside the
   * window — the series begins before they owned anything.
   *
   * Reporting it as performance produced a card that contradicted itself:
   * `deltaAbs` became the entire portfolio ("+EUR 8,070 gain") while `deltaPct`
   * fell to 0 because of the guard below ("0.00%"). Seen on a real account.
   * Neither number was wrong in isolation; together they told a member they had
   * made money they had merely ADDED.
   */
  const hasBaseline = startValue > EPSILON;
  // Zero rather than currentValue when there is no baseline. A "gain" equal to
  // everything you own is not a gain, and a trader acting on it is acting on
  // nothing.
  const deltaAbs = hasBaseline ? currentValue - startValue : 0;
  const deltaPct = hasBaseline ? deltaAbs / startValue : 0;

  let peak = startValue;
  let maxDrawdownPct = 0;

  for (const p of sorted) {
    if (p.v > peak) {
      peak = p.v;
    }
    if (peak > EPSILON) {
      const drawdown = (p.v - peak) / peak;
      if (drawdown < maxDrawdownPct) {
        maxDrawdownPct = drawdown;
      }
    }
  }

  return {
    startValue,
    currentValue,
    deltaAbs,
    deltaPct,
    maxDrawdownPct,
    hasBaseline,
  };
}

/**
 * Compute category allocations (value weights) from item snapshots.
 */
export function computeAllocationsFromItems(
  items: PortfolioItemSnapshot[],
): CategoryAllocation[] {
  const totals = new Map<string, number>();

  for (const item of items) {
    const value =
      typeof item.currentValue === 'number'
        ? item.currentValue
        : typeof item.estimatedValue === 'number'
        ? item.estimatedValue
        : 0;

    const prev = totals.get(item.category) ?? 0;
    totals.set(item.category, prev + value);
  }

  const grandTotal = Array.from(totals.values()).reduce(
    (sum, v) => sum + v,
    0,
  );

  const allocations: CategoryAllocation[] = [];
  for (const [category, totalValue] of totals.entries()) {
    allocations.push({
      category,
      totalValue,
      weight: grandTotal > EPSILON ? totalValue / grandTotal : 0,
    });
  }

  allocations.sort((a, b) => b.totalValue - a.totalValue);
  return allocations;
}

/**
 * Compute a diversification score in [0,1] from category allocations using
 * a normalized Herfindahl-Hirschman-like index:
 *
 *   diversification = 1 - sum(w_i^2)
 */
export function computeDiversificationScore(
  allocations: CategoryAllocation[],
): number {
  if (!allocations.length) {
    return 0;
  }
  const sumSq = allocations.reduce((sum, a) => sum + a.weight * a.weight, 0);
  const score = 1 - sumSq;
  return clamp(score, 0, 1);
}

/**
 * Split items into winners, losers, neutral based on 1D change threshold.
 */
export function computeWinnersAndLosers(
  items: PortfolioItemSnapshot[],
  thresholdPct = 0.02,
): WinnersLosersBucket {
  const winners: PortfolioItemSnapshot[] = [];
  const losers: PortfolioItemSnapshot[] = [];
  const neutral: PortfolioItemSnapshot[] = [];

  for (const item of items) {
    const pct = item.change1dPct;
    if (typeof pct !== 'number') {
      neutral.push(item);
      continue;
    }
    if (pct > thresholdPct) {
      winners.push(item);
    } else if (pct < -thresholdPct) {
      losers.push(item);
    } else {
      neutral.push(item);
    }
  }

  winners.sort((a, b) => (b.change1dPct ?? 0) - (a.change1dPct ?? 0));
  losers.sort((a, b) => (a.change1dPct ?? 0) - (b.change1dPct ?? 0));

  return { winners, losers, neutral };
}

/**
 * Aggregate set completion into a [0,1] portfolio completeness score.
 */
export function computeCompletenessScore(
  sets: SetCompletion[],
): number {
  if (!sets.length) {
    return 0;
  }

  let weightedSum = 0;
  let totalCards = 0;

  for (const set of sets) {
    const owned = Math.max(0, set.ownedCount);
    const total = Math.max(1, set.totalCount);
    const completion = clamp(owned / total, 0, 1);

    weightedSum += completion * total;
    totalCards += total;
  }

  if (totalCards === 0) {
    return 0;
  }
  return clamp(weightedSum / totalCards, 0, 1);
}

/**
 * Compute an aggregate rarity score in [0,1] across all items.
 */
export function computeAverageRarityScore(
  items: PortfolioItemSnapshot[],
): number {
  if (!items.length) {
    return 0;
  }

  let sum = 0;
  let count = 0;

  for (const item of items) {
    if (typeof item.rarityScore === 'number') {
      sum += clamp(item.rarityScore, 0, 1);
      count += 1;
    }
  }

  if (count === 0) {
    return 0;
  }

  return clamp(sum / count, 0, 1);
}

/**
 * Determine portfolio tier from three dimensions:
 * - rarityScore
 * - completenessScore
 * - diversificationScore
 */
export function computeTierFromScores(
  rarityScore: number,
  completenessScore: number,
  diversificationScore: number,
): PortfolioTierSummary {
  const rarity = clamp(rarityScore, 0, 1);
  const completeness = clamp(completenessScore, 0, 1);
  const diversification = clamp(diversificationScore, 0, 1);

  const composite =
    0.5 * rarity +
    0.3 * completeness +
    0.2 * diversification;

  let tier: Tier = 'Unranked';

  if (composite >= 0.8 && rarity >= 0.75 && completeness >= 0.7) {
    tier = 'Diamond';
  } else if (composite >= 0.55) {
    tier = 'Gold';
  } else if (composite >= 0.3) {
    tier = 'Silver';
  } else {
    tier = 'Unranked';
  }

  return {
    tier,
    rarityScore: rarity,
    completenessScore: completeness,
    diversificationScore: diversification,
  };
}

/**
 * High-level aggregation: compute a full portfolio snapshot from basic ingredients.
 *
 * You can feed:
 * - series: portfolio value history
 * - items: enriched item snapshots
 * - sets: set completion metrics
 */
export function computePortfolioSnapshot(args: {
  series: TimeSeriesPoint[];
  items: PortfolioItemSnapshot[];
  sets?: SetCompletion[];
}): PortfolioSnapshot {
  const { series, items } = args;
  const sets = args.sets ?? [];

  const pl = computePLFromSeries(series);
  const allocations = computeAllocationsFromItems(items);
  const winnersLosers = computeWinnersAndLosers(items);
  const completenessScore = computeCompletenessScore(sets);
  const rarityScore = computeAverageRarityScore(items);
  const diversificationScore = computeDiversificationScore(allocations);
  const tierSummary = computeTierFromScores(
    rarityScore,
    completenessScore,
    diversificationScore,
  );

  return {
    pl,
    series: [...series].sort(
      (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime(),
    ),
    allocations,
    winnersLosers,
    tierSummary,
    items,
  };
}
