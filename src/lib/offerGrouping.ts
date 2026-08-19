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
 *
 * ⚠️ COUNT AND SPREAD COME FROM THE `population` ARGUMENT, NOT FROM THE SECTION.
 * A seller with three bids who counters one splits that listing across two
 * sections — the countered bid is now "waiting on them" while the other two
 * still need an answer. Counted per section, the banner would say "2 bids"
 * while three are live: a number stated to a seller who is choosing, that is
 * simply wrong. The caller passes every ACTIVE offer as the population, so the
 * banner states the truth about the listing in whichever section it appears.
 */

export interface GroupableOffer {
  id: string;
  listing_id: string;
  amount: number;
}

export interface OfferGroupMeta {
  /** How many ACTIVE offers share this listing, across every section — not how
   *  many landed in this one. 1 = no competition, no banner. */
  size: number;
  /** True for the first card of this listing WITHIN ITS SECTION, and only when
   *  the listing has competition at all. The banner is drawn once per section
   *  the listing appears in, so a lone countered bid still says what it is one
   *  of, rather than looking unrelated to the two sitting above it. */
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
 * @param offers      one section, already in its priority order.
 * @param population  every offer the count and spread should describe — pass
 *                    ALL active offers, not just this section. Defaults to the
 *                    section, which is right only when there is one section.
 *
 * Pure and total: an empty list returns empty, and every input id appears
 * exactly once in the output.
 */
export function groupCompetingOffers<T extends GroupableOffer>(
  offers: readonly T[],
  population: readonly GroupableOffer[] = offers,
): { ordered: T[]; meta: Map<string, OfferGroupMeta> } {
  // How the listing looks as a whole — the numbers the banner states.
  const whole = new Map<string, { size: number; low: number; high: number }>();
  for (const o of population) {
    const amount = o.amount ?? 0;
    const seen = whole.get(o.listing_id);
    if (seen) {
      seen.size += 1;
      if (amount < seen.low) seen.low = amount;
      if (amount > seen.high) seen.high = amount;
    } else {
      whole.set(o.listing_id, { size: 1, low: amount, high: amount });
    }
  }

  // How the listing looks in THIS section — which cards to place adjacently.
  const inSection = new Map<string, T[]>();
  for (const o of offers) {
    const list = inSection.get(o.listing_id);
    if (list) list.push(o);
    else inSection.set(o.listing_id, [o]);
  }

  const ordered: T[] = [];
  const meta = new Map<string, OfferGroupMeta>();
  const emitted = new Set<string>();

  for (const o of offers) {
    if (emitted.has(o.listing_id)) continue;
    emitted.add(o.listing_id);

    // `slice` via spread: this runs inside a useMemo over state React may
    // reuse, so the caller's array must not be sorted in place.
    const group = [...(inSection.get(o.listing_id) ?? [o])]
      .sort((a, b) => (b.amount ?? 0) - (a.amount ?? 0));
    // Falls back to the card's own amount when the caller passed a population
    // that does not contain it — a wrong population must not read as a zero
    // bid on screen.
    const stats = whole.get(o.listing_id)
      ?? { size: group.length, low: o.amount ?? 0, high: o.amount ?? 0 };

    group.forEach((g, i) => {
      ordered.push(g);
      meta.set(g.id, {
        size: stats.size,
        isFirst: i === 0 && stats.size > 1,
        low: stats.low,
        high: stats.high,
      });
    });
  }

  return { ordered, meta };
}
