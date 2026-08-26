export interface PortfolioLikeItem {
  id: string;
  name: string;
  currentValue: number; // estimated market value (EUR)
  costBasis: number; // total amount paid (EUR)
}

export interface PortfolioPLSummary {
  totalCurrentValue: number;
  totalCostBasis: number;
  totalUnrealizedPL: number;
  totalUnrealizedPLPercent: number; // overall ROI in %
}

export interface ItemPL extends PortfolioLikeItem {
  unrealizedPL: number;
  unrealizedPLPercent: number;
}

/**
 * Safe numeric conversion with basic guards.
 */
function toNumber(value: unknown): number {
  if (value === null || value === undefined) return 0;
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return n;
}

/** Value sources that rest on market data rather than on somebody's opinion.
 *  Must match MARKET_SOURCES in src/components/ValueSourceChip.tsx and
 *  server/tests/test_leaderboard_value_parity.py. */
const MARKET_SOURCES = new Set(['catalog_daily', 'catalog_model', 'quick_scan']);

export interface PortfolioValueSplit {
  /** What the member PAID, where a purchase price is on file. A fact. */
  purchaseTotal: number;
  /** Comp/model-backed value. What the market says. */
  marketTotal: number;
  /** Value resting on a number nobody checked — typed by the member, or
   *  produced by a vision scan. */
  estimateTotal: number;
  /** Items behind each figure, so the UI can say "3 of 12 items". */
  purchaseCount: number;
  marketCount: number;
  estimateCount: number;
}

/**
 * Split a collection into the THREE numbers it actually has: what you paid,
 * what the market says, and what somebody guessed.
 *
 * Decided 2026-08-19. They are not three versions of one figure — one is a
 * fact about the past, one is a claim about the market, and one is an opinion —
 * and collapsing them is how `unrealized_pl` came to measure model drift
 * instead of profit (docs/ARCHITECTURE.md, "Money math").
 *
 * `estimateTotal` is deliberately SEPARATE from `marketTotal` rather than
 * excluded: for the 40+ categories with no sold-comp source, the estimate is
 * all a member has, and dropping it would show them a portfolio worth less
 * than they know it is. Include and mark, never hide.
 *
 * An unknown/absent `valueSource` counts as an ESTIMATE, not as market. The
 * conservative side is the one that under-claims.
 */
export function splitPortfolioByValueSource(
  rawItems: Partial<PortfolioLikeItem & { valueSource?: string; hasPurchasePrice?: boolean }>[],
): PortfolioValueSplit {
  const out: PortfolioValueSplit = {
    purchaseTotal: 0, marketTotal: 0, estimateTotal: 0,
    purchaseCount: 0, marketCount: 0, estimateCount: 0,
  };
  for (const item of rawItems) {
    const value = toNumber(item.currentValue);
    if (MARKET_SOURCES.has(item.valueSource ?? '')) {
      out.marketTotal += value;
      out.marketCount += 1;
    } else {
      out.estimateTotal += value;
      out.estimateCount += 1;
    }
    // Only a REAL purchase price counts. Without `hasPurchasePrice` the server
    // falls back to the earliest prediction as cost basis, and summing that
    // into "what you paid" reports money the member never spent.
    if (item.hasPurchasePrice) {
      out.purchaseTotal += toNumber(item.costBasis);
      out.purchaseCount += 1;
    }
  }
  return out;
}

/**
 * Compute portfolio-level P/L summary.
 */
export function calculatePortfolioPLSummary(
  rawItems: Partial<PortfolioLikeItem>[]
): PortfolioPLSummary {
  let totalCurrentValue = 0;
  let totalCostBasis = 0;

  for (const item of rawItems) {
    const currentValue = toNumber(item.currentValue);
    const costBasis = toNumber(item.costBasis);

    totalCurrentValue += currentValue;
    totalCostBasis += costBasis;
  }

  const totalUnrealizedPL = totalCurrentValue - totalCostBasis;

  const totalUnrealizedPLPercent =
    totalCostBasis > 0 ? (totalUnrealizedPL / totalCostBasis) * 100 : 0;

  return {
    totalCurrentValue,
    totalCostBasis,
    totalUnrealizedPL,
    totalUnrealizedPLPercent,
  };
}

/**
 * Compute per-item P/L and ROI.
 */
export function calculatePerItemPL(
  rawItems: Partial<PortfolioLikeItem>[]
): ItemPL[] {
  return rawItems.map((item, index) => {
    const currentValue = toNumber(item.currentValue);
    const costBasis = toNumber(item.costBasis);

    const unrealizedPL = currentValue - costBasis;
    const unrealizedPLPercent =
      costBasis > 0 ? (unrealizedPL / costBasis) * 100 : 0;

    return {
      id: item.id ?? String(index),
      name: (item.name as string) ?? "Unnamed item",
      currentValue,
      costBasis,
      unrealizedPL,
      unrealizedPLPercent,
    };
  });
}

/**
 * Simple helper to sort items by best performers (highest ROI first).
 */
export function sortItemsByPL(items: ItemPL[]): ItemPL[] {
  return [...items].sort(
    (a, b) => b.unrealizedPLPercent - a.unrealizedPLPercent
  );
}

/** One ranked position plus the population it was ranked out of. */
export type RankedPositions<T> = {
  ranked: T[];
  /** Items whose cost basis is REAL — the population the ranking describes. */
  counted: number;
  /** Items excluded for having no real cost basis. Must be shown, not hidden. */
  missingBasis: number;
};

/**
 * Rank positions by unrealised P/L for the analytics "Positions" card.
 *
 * Extracted from the screen so it can be tested: this function decides which
 * numbers a member is shown as PROFIT, and that decision is exactly the kind
 * that should not live untested inside a `useMemo`.
 *
 * Two rules it enforces, both of which the screen would otherwise get wrong:
 *
 * 1. **`hasPurchasePrice` gates the ranking.** The server falls back to the
 *    earliest PREDICTION as cost basis when an item has no purchase price, so
 *    `unrealizedPL` on those rows measures how far the MODEL moved. It arrives
 *    as the same number, in the same field, and looks identical. Ranking is a
 *    headline, and `splitPortfolioByValueSource`'s own note applies: summing
 *    these "reports money the member never spent".
 * 2. **Sort by ABSOLUTE move, not by gain.** Descending gain buries every loss
 *    at the bottom, and a loss is the position a member most needs to act on.
 *
 * `costBasis > 0` is also required — a zero basis makes the percentage the
 * caller renders a divide-by-zero.
 */
export function rankPositions<
  T extends {
    hasPurchasePrice?: boolean;
    costBasis?: number;
    unrealizedPL?: number;
  },
>(items: T[], limit = 6): RankedPositions<T> {
  const withBasis = items.filter(
    (i) =>
      i.hasPurchasePrice === true &&
      typeof i.costBasis === "number" &&
      i.costBasis > 0 &&
      typeof i.unrealizedPL === "number",
  );
  const ranked = [...withBasis].sort(
    (a, b) => Math.abs(b.unrealizedPL ?? 0) - Math.abs(a.unrealizedPL ?? 0),
  );
  return {
    ranked: ranked.slice(0, limit),
    counted: withBasis.length,
    missingBasis: items.length - withBasis.length,
  };
}
