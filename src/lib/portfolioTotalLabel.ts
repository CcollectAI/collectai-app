/**
 * The "Portfolio value" line on the Items tab.
 *
 * It used to be `dataSource.reduce(...)` over the pages loaded so far
 * (ITEMS_PAGE_SIZE = 20), rendered under Home's own label
 * (`home.portfolio_value`). Over 20 items the Items tab therefore printed a
 * SMALLER number than Home for the same fact, and it grew as the member
 * scrolled — the 2026-09-12 €1.288-vs-€1.348 bug re-created client-side (class
 * sweep, 2026-09-16).
 *
 * Rules, in order:
 *  1. The server's total (`/portfolio/overview.total_value`, the same source
 *     Home uses) wins whenever it is available — including 0, which is a real
 *     answer, not a missing one.
 *  2. Otherwise the loaded rows, marked `+` when more pages exist, so a partial
 *     number never looks whole (the Events tab's convention).
 *  3. Both go through `fmtCurrency`, which CONVERTS the EUR amount into the
 *     member's currency. `formatPrice` would have labelled euros with their
 *     symbol.
 */
import { fmtCurrency } from './format';
import type { Settings } from './settings';

type MoneySettings = Pick<Settings, 'currency' | 'numberLocale' | 'fxRates'>;

export function portfolioTotalLabel(
  serverTotalEur: number | null | undefined,
  loadedTotalEur: number,
  hasMore: boolean,
  settings: MoneySettings,
): string {
  if (typeof serverTotalEur === 'number' && Number.isFinite(serverTotalEur)) {
    return fmtCurrency(serverTotalEur, settings);
  }
  return `${fmtCurrency(loadedTotalEur, settings)}${hasMore ? '+' : ''}`;
}
