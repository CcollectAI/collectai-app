/**
 * Competing bids on one listing, put next to each other.
 *
 * THE GAP THIS CLOSES (docs/P2P_MARKETPLACE_SPEC.md, "Two gaps, stated rather
 * than left to be discovered"): the data model allows many offers per listing,
 * but the screen is a flat list across ALL your listings ranked by "needs you"
 * then recency — so two bids on the same item can sit ten cards apart with
 * unrelated trades between them. Choosing between them is the single most
 * common decision a seller makes, and the screen made it the hardest one.
 *
 * The spec also records what CANNOT help: comparing on distance is impossible
 * by construction, since addresses are only collectable after `accepted`. At
 * decision time the seller has price and age. So the group header carries
 * exactly that — how many, and the spread.
 *
 * WHY NOT A SEPARATE SECTION PER LISTING: the three sections (needs you /
 * waiting on them / closed) are a PRIORITY order, and a listing-scoped section
 * would outrank it — a member's own move could end up below a listing they are
 * not being asked about. Grouping happens INSIDE a section, and the group takes
 * the position of its best-placed member, so priority still wins.
 */

export interface GroupableOffer {
  id: string;
  listing_id: string;
  amount: number;
}

export interface OfferGroupMeta {
  /** How many offers in this section share the listing. 1 = not a group. */
  size: number;
  /** True for the first card of a multi-offer group — the only one that draws
   *  the header, so the banner appears once rather than per card. */
  isFirst: boolean;
  low: number;
  high: number;
}

/**
 * Reorder one section so competing bids are adjacent, and describe each group.
 *
 * Rules, in order:
 *  - a group takes the position of its FIRST member in the incoming order, so
 *    the section's existing ranking (needs-you, then recency) still decides
 *    where the group sits;
 *  - inside a group, the highest bid comes first — that is the one a seller
 *    reads first, and the order that makes the spread obvious;
 *  - single-offer listings are untouched.
 *
 * Pure and total: an empty list returns empty, and every input id appears
 * exactly once in the output.
 */
export function groupCompetingOffers<T extends GroupableOffer>(
  offers: readonly T[],
): { ordered: T[]; meta: Map<string, OfferGroupMeta> } {
  const byListing = new Map<string, T[]>();
  for (const o of offers) {
    const list = byListing.get(o.listing_id);
    if (list) list.push(o);
    else byListing.set(o.listing_id, [o]);
  }

  const ordered: T[] = [];
  const meta = new Map<string, OfferGroupMeta>();
  const emitted = new Set<string>();

  for (const o of offers) {
    if (emitted.has(o.listing_id)) continue;
    emitted.add(o.listing_id);

    const group = byListing.get(o.listing_id) ?? [o];
    if (group.length === 1) {
      ordered.push(group[0]);
      meta.set(group[0].id, { size: 1, isFirst: false, low: group[0].amount, high: group[0].amount });
      continue;
    }

    // Highest first. `slice()` so the caller's array is never mutated — this
    // runs inside a useMemo over state that React may reuse.
    const sorted = [...group].sort((a, b) => (b.amount ?? 0) - (a.amount ?? 0));
    const amounts = sorted.map((g) => g.amount ?? 0);
    const low = Math.min(...amounts);
    const high = Math.max(...amounts);
    sorted.forEach((g, i) => {
      ordered.push(g);
      meta.set(g.id, { size: sorted.length, isFirst: i === 0, low, high });
    });
  }

  return { ordered, meta };
}
