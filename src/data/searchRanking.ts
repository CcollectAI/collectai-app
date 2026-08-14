/**
 * Put what you collect first.
 *
 * A member who follows Pokémon and searches "charizard" wants their categories
 * at the top; the same query from a Warhammer collector should not look
 * identical. Followed categories have driven the add flow, the scan classifier,
 * market movers, events and deal discovery since May — search was the one place
 * they were never read.
 *
 * PURE, and deliberately not a hook. Ranking is a data transform, so it lives
 * where a test can reach it without pulling a screen's dependency graph into
 * jest — the lesson `moverFormat.ts` was extracted for, after a Pro gate
 * dragged the RevenueCat SDK into a pure-logic suite and the whole file stopped
 * running.
 *
 * WHAT THIS IS NOT
 * ----------------
 * Not a filter. Nothing is hidden: a result outside your categories still
 * appears, just below the ones inside them. Filtering search by follows would
 * mean a member who follows only Pokémon could never find a Warhammer listing
 * they searched for by name, which is a worse failure than an unhelpful order.
 *
 * Not a relevance score either. The server already ordered each list by its own
 * relevance, and this only PARTITIONS that order — followed first, everything
 * else after, with the server's sequence preserved inside both halves. A stable
 * partition cannot make a good match disappear beneath a bad one that happens
 * to be in a followed category.
 */

/** Anything with a category slug on it. `users` have none and are never ranked. */
type Categorised = { category?: string | null };

/**
 * Stable partition: entries whose category is followed, then the rest, each
 * keeping the order they arrived in.
 *
 * `Array.prototype.sort` is stable in every JS engine since ES2019, but this
 * does not use it — a comparator returning 0 for "both followed" invites a
 * future edit to add a tiebreak and quietly re-order the server's relevance.
 * Two passes say the intent out loud.
 */
export function partitionByFollowed<T extends Categorised>(
  rows: readonly T[],
  followed: ReadonlySet<string>,
): T[] {
  if (!rows.length || followed.size === 0) return [...rows];
  const inside: T[] = [];
  const outside: T[] = [];
  for (const row of rows) {
    if (row.category && followed.has(row.category)) inside.push(row);
    else outside.push(row);
  }
  return [...inside, ...outside];
}

/** The category list itself keys on `id`, not `category`. */
export function partitionCategoriesByFollowed<T extends { id: string }>(
  rows: readonly T[],
  followed: ReadonlySet<string>,
): T[] {
  if (!rows.length || followed.size === 0) return [...rows];
  const inside: T[] = [];
  const outside: T[] = [];
  for (const row of rows) {
    if (followed.has(row.id)) inside.push(row);
    else outside.push(row);
  }
  return [...inside, ...outside];
}

export type RankableResults = {
  items: Categorised[];
  catalog: Categorised[];
  events: Categorised[];
  categories: { id: string }[];
  [key: string]: unknown;
};

/**
 * Rank every categorised list in a search response.
 *
 * `users` are returned untouched on purpose — a person has no category, and
 * inventing one would be the kind of guess that puts the wrong name on top.
 *
 * Returns the SAME object when there is nothing to do (no follows), so a
 * caller memoising on identity does not re-render for a no-op.
 */
export function rankSearchResults<T extends RankableResults>(
  results: T | null,
  followed: ReadonlySet<string>,
): T | null {
  if (!results || followed.size === 0) return results;
  return {
    ...results,
    items: partitionByFollowed(results.items ?? [], followed),
    catalog: partitionByFollowed(results.catalog ?? [], followed),
    events: partitionByFollowed(results.events ?? [], followed),
    categories: partitionCategoriesByFollowed(results.categories ?? [], followed),
  };
}
