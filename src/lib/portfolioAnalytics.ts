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
