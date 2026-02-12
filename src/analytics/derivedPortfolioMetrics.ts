/**
 * derivedPortfolioMetrics.ts
 *
 * Higher-level analytics helpers on top of the base PortfolioSnapshot.
 *
 * These functions are meant to power:
 * - Portfolio + Analytics screens
 * - Leaderboard / badge logic
 * - Future insights (e.g. "you are overexposed to X", "top 3 winners")
 *
 * They are deliberately pure and synchronous: call them in your hooks and
 * screens with the current PortfolioSnapshot.
 */

import type {
  PortfolioSnapshot,
  PortfolioItemSnapshot,
  CategoryAllocation,
} from './portfolioMetrics';
import type { ExtendedPortfolioItem } from '@/../types/api';

export type RoiByCategory = {
  category: string;
  roiPct: number; // -1..+∞
  totalBase: number;
  totalNow: number;
};

export type TopMoveDirection = 'gainers' | 'losers';

export type TopMove = {
  itemId: string;
  name: string;
  category: string;
  currentValue: number;
  change1dPct: number;
};

export type DiversificationScores = {
  herfindahlIndex: number; // 0..1, higher = more concentrated
  diversificationScore: number; // 0..1, higher = more diversified
};

export type PortfolioHealthSummary = {
  totalValue: number;
  totalCostBasis: number;
  unrealizedPl: number;
  unrealizedPlPct: number | null;
  roiByCategory: RoiByCategory[];
  topGainers: TopMove[];
  topLosers: TopMove[];
  diversification: DiversificationScores | null;
};

function safeNumber(x: unknown, fallback = 0): number {
  const n = typeof x === 'number' ? x : Number(x);
  return Number.isFinite(n) ? n : fallback;
}

function toCurrency(n: number | null | undefined): number {
  if (n == null) return 0;
  return safeNumber(n, 0);
}

/**
 * Compute category-level ROI using costBasis if available, otherwise
 * reconstruct a synthetic base from 1D/7D change where possible.
 */
export function computeRoiByCategory(
  items: PortfolioItemSnapshot[],
): RoiByCategory[] {
  const buckets: Record<
    string,
    { base: number; now: number }
  > = {};

  for (const item of items) {
    const category = item.category ?? 'Uncategorized';
    const now =
      toCurrency(item.currentValue) ||
      toCurrency(item.estimatedValue);

    if (now <= 0) continue;

    let base = 0;

    const costBasis = item.costBasis ?? (item as ExtendedPortfolioItem).purchasePrice;
    if (typeof costBasis === 'number' && costBasis > 0) {
      base = costBasis;
    } else {
      const c7 = item.change7dPct;
      const c1 = item.change1dPct;

      if (typeof c7 === 'number' && c7 !== 0) {
        base = now / (1 + c7);
      } else if (typeof c1 === 'number' && c1 !== 0) {
        base = now / (1 + c1);
      } else {
        base = now;
      }
    }

    if (!buckets[category]) {
      buckets[category] = { base: 0, now: 0 };
    }
    buckets[category].base += base;
    buckets[category].now += now;
  }

  return Object.entries(buckets).map(([category, v]) => {
    const { base, now } = v;
    const roiPct = base > 0 ? (now - base) / base : 0;
    return {
      category,
      roiPct,
      totalBase: base,
      totalNow: now,
    };
  });
}

/**
 * Return the top N gainers or losers based on 1D percentage change.
 */
export function getTopMoves(
  items: PortfolioItemSnapshot[],
  direction: TopMoveDirection,
  limit = 3,
): TopMove[] {
  const withChange = items
    .map((item) => {
      const change1dPct = safeNumber(
        item.change1dPct,
        0,
      );
      return {
        item,
        change1dPct,
      };
    })
    .filter((row) => row.change1dPct !== 0);

  if (!withChange.length) return [];

  const sorted =
    direction === 'gainers'
      ? withChange.sort(
          (a, b) => b.change1dPct - a.change1dPct,
        )
      : withChange.sort(
          (a, b) => a.change1dPct - b.change1dPct,
        );

  const chosen = sorted.slice(0, limit);

  return chosen.map((row) => ({
    itemId: String(row.item.id),
    name: row.item.name ?? 'Untitled item',
    category: row.item.category ?? 'Uncategorized',
    currentValue:
      toCurrency(row.item.currentValue) ||
      toCurrency(row.item.estimatedValue),
    change1dPct: row.change1dPct,
  }));
}

/**
 * Diversification: compute Herfindahl index from category allocations,
 * then map it to a 0..1 diversification score (1 = perfectly diversified).
 */
export function computeDiversificationFromAllocations(
  allocations: CategoryAllocation[],
): DiversificationScores | null {
  if (!allocations.length) return null;

  const total = allocations.reduce(
    (sum, a) => sum + toCurrency(a.totalValue),
    0,
  );
  if (total <= 0) {
    return {
      herfindahlIndex: 1,
      diversificationScore: 0,
    };
  }

  let h = 0;
  for (const alloc of allocations) {
    const share = toCurrency(alloc.totalValue) / total;
    h += share * share;
  }

  const diversificationScore = 1 - h;

  return {
    herfindahlIndex: h,
    diversificationScore,
  };
}

/**
 * High-level portfolio health summary based on a snapshot.
 *
 * This is the main entry point you can call from screens:
 *   const summary = summarizePortfolioHealth(snapshot);
 */
export function summarizePortfolioHealth(
  snapshot: PortfolioSnapshot | null | undefined,
): PortfolioHealthSummary | null {
  if (!snapshot) return null;

  const items = snapshot.items ?? [];
  const allocations = snapshot.allocations ?? [];
  const pl = snapshot.pl ?? null;

  let totalValue = 0;
  let totalCostBasis = 0;

  for (const item of items) {
    const now =
      toCurrency(item.currentValue) ||
      toCurrency(item.estimatedValue);

    const costBasis =
      item.costBasis ??
      (item as ExtendedPortfolioItem).purchasePrice ??
      null;

    totalValue += now;
    if (typeof costBasis === 'number' && costBasis > 0) {
      totalCostBasis += costBasis;
    }
  }

  const unrealizedPl =
    totalCostBasis > 0 ? totalValue - totalCostBasis : 0;
  const unrealizedPlPct =
    totalCostBasis > 0
      ? unrealizedPl / totalCostBasis
      : pl?.deltaPct ?? null;

  const roiByCategory = computeRoiByCategory(items);
  const topGainers = getTopMoves(items, 'gainers', 3);
  const topLosers = getTopMoves(items, 'losers', 3);
  const diversification =
    computeDiversificationFromAllocations(allocations);

  return {
    totalValue,
    totalCostBasis,
    unrealizedPl,
    unrealizedPlPct,
    roiByCategory,
    topGainers,
    topLosers,
    diversification,
  };
}
