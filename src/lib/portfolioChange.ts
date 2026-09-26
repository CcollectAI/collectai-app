/**
 * The headline change on Home's Portfolio card.
 *
 * 2026-09-26: the change was last point minus first, so ADDING a EUR 25 item
 * read as "+EUR 25" of gain. /portfolio/timeseries now also sends
 * `market_change` — the value change of what was already owned when the range
 * opened — and that is the number shown when present.
 */
import type { TimeSeriesPoint } from "@/components/PortfolioLineChart";

/** `market_change` from /portfolio/timeseries, or null when absent (older server,
 *  proxy). It is the change in value of what was ALREADY owned when the range
 *  opened — the raw last-minus-first counted an item you ADDED as a gain. */
export function extractMarketChange(raw: unknown): number | null {
  const v = (raw as Record<string, unknown> | null)?.market_change;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** What the change is measured AGAINST. With `market_change` that is what the
 *  items were worth when they entered the range — `current - market_change` —
 *  not the chart's first point: on 90D the chart starts at EUR 0 (nothing owned
 *  yet), which printed "-EUR 35 (0,00%)" (device walk, 2026-09-26). Without it,
 *  the range's opening value, as before. */
export function changeBasis(startVal: number, endVal: number, marketChange: number | null): number {
  return marketChange != null ? endVal - marketChange : startVal;
}

/** Headline change for the chosen range: market movement when the server
 *  reports it, else last minus first, as a share of `changeBasis`. */
export function portfolioChange(series: TimeSeriesPoint[], marketChange: number | null) {
  if (!series.length) return { total: 0, delta: 0, deltaPct: 0 };
  const sorted = [...series].sort((a, b) => new Date(a.t).getTime() - new Date(b.t).getTime());
  const startVal = sorted[0].v;
  const endVal = sorted[sorted.length - 1].v;
  const d = marketChange ?? endVal - startVal;
  const basis = changeBasis(startVal, endVal, marketChange);
  return { total: endVal, delta: d, deltaPct: basis > 0 ? d / basis : 0 };
}

