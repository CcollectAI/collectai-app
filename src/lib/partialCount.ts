/**
 * How a count drawn from loaded pages is written down.
 *
 * A screen that pages can only count what it has downloaded, so printing
 * `list.length` states the first page as the whole answer — and the number then
 * GROWS as the member scrolls, which is how the Items tab's portfolio total and
 * the Member Marketplace header were both wrong (class sweep, 2026-09-16). The
 * playbook's rule: *the confidence travels with the number, not in a comment*
 * (`docs/ui-playbook.md`).
 *
 * One function so the marking is one decision. The Events tab had written the
 * `+` inline four times and got two of them — `Past Events (N)` and
 * `Events on <date> (N)` are client-side splits of the SAME paginated list as
 * the two that were marked, so they were partial in exactly the same way.
 *
 * Prefer a real total when the server gives you one: this is the fallback for
 * when it does not (see `portfolioTotalLabel`, which tries the server first).
 */
export function partialCount(loadedCount: number, hasMore: boolean): string {
  return `${loadedCount}${hasMore ? '+' : ''}`;
}
