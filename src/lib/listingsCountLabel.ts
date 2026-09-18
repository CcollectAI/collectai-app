/**
 * The result count on the Member Marketplace (`app/listings.tsx`).
 *
 * The screen pages at `PAGE_SIZE = 24` through `usePaginatedList`, and the
 * header printed `listings.length` as though it were the total: a member
 * browsing 200 listings read "24 listings", and the number GREW as they
 * scrolled. Same defect as the Items tab's portfolio total before
 * `portfolioTotalLabel` (class sweep, 2026-09-16) — and the playbook states the
 * rule as *the confidence travels with the number, not in a comment*
 * (`docs/ui-playbook.md`).
 *
 * There is no server total to prefer here: `GET /marketplace/listings` returns
 * `ListingListResponse { listings }` and no count, so rule 1 of
 * `portfolioTotalLabel` has nothing to use and rule 2 applies — mark the
 * partial number `+` so it never looks whole. If an exact total is ever wanted,
 * it has to come from the server; counting on the client can only ever count
 * what was downloaded.
 *
 * The plural follows what the member is being told exists, not the digits: with
 * more pages waiting there is certainly more than one, so "1+ listings" — never
 * "1+ listing".
 */
import { partialCount } from './partialCount';

export function listingsCountLabel(loadedCount: number, hasMore: boolean): string {
  const plural = loadedCount === 1 && !hasMore ? '' : 's';
  return `${partialCount(loadedCount, hasMore)} listing${plural}`;
}
