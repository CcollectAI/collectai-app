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

/** Headline change for the chosen range: market movement when the server
 *  reports it, else last minus first. Percent is against the range's opening
 *  value, as before. */
export function portfolioChange(series: TimeSeriesPoint[], marketChange: number | null) {
  if (!series.length) return { total: 0, delta: 0, deltaPct: 0 };
  const sorted = [...series].sort((a, b) => new Date(a.t).getTime() - new Date(b.t).getTime());
  const startVal = sorted[0].v;
  const endVal = sorted[sorted.length - 1].v;
  const d = marketChange ?? endVal - startVal;
  return { total: endVal, delta: d, deltaPct: startVal > 0 ? d / startVal : 0 };
}

