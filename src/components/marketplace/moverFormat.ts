/**
 * Pure display helpers for Market Movers — no React, no hooks, no SDKs.
 *
 * Extracted from MarketMoversSection 2026-08-13. `__tests__/components/
 * marketMovers.test.ts` exercises these functions only, but importing them
 * from the component pulled the component's whole dependency graph into the
 * test — and the moment the component started reading `useBillingLimits` for
 * the Pro gate, that graph included the RevenueCat SDK, which jest does not
 * transform. The suite stopped RUNNING: not a failed assertion but a module
 * parse error, which is the kind of red that gets waved through as config
 * noise.
 *
 * A pure seam has no such graph. Same reason `src/data/personalizedInsights.ts`
 * exists.
 */
import type { TopMover } from '@/api/dataMoatApi';

/**
 * Price floor for the PERCENTAGE ranking, shared by the Market tab widget and
 * the full screen so the two cannot show different lists for the same question.
 *
 * `mv_market_top_movers` already drops thin data (comps_30d >= 5, days_30d >= 3,
 * a 5x outlier cap) but its only price floor is `med_30d >= 1`, so a EUR 1 card
 * competes in a list about where the market moved. Measured on prod
 * 2026-08-13: the top-20 gainers by percentage were led by a EUR 1.77 move on a
 * EUR 3.60 card and 11 of 20 were under EUR 10, while a EUR 569.71 move ranked
 * 13th.
 *
 * Percentage ranking only. Ranking by euros already sorts trivial moves to the
 * bottom, so a floor there would hide data for nothing. Anything hidden is
 * stated on screen — a silent filter reads as "this is everything".
 */
export const PCT_MIN_PRICE_EUR = 5;

/** Catalog item_key for deep-linking (strip the `category:` prefix when unmatched). */
export function moverKey(m: TopMover): string {
  return m.item_key ?? m.item_ref.split(':').slice(1).join(':');
}

// Words kept lowercase inside a title (never as the first word).
const MINOR_WORDS = new Set(['of', 'the', 'and', 'a', 'an', 'to', 'in', 'on', 'for', 'from', 'with']);

/**
 * Turn a catalog slug into something readable.
 *
 * 7 of the 20 rows GET /catalog/top-movers returns have `title: null` and
 * `in_catalog: false` — price data exists for an item_ref the catalog has no
 * row for. That is the known catalog-reachability gap (CLAUDE.md, "The catalog
 * ↔ price crosswalk": mtg and yugioh refs that no tcgcsv-derived catalog row
 * covers), and closing it is a data problem, not a display one.
 *
 * Until then the fallback showed the raw slug, so a third of the Market Movers
 * feed read `95486586-elemental-hero-core`. The slug already contains the name,
 * so derive it: drop a leading numeric id (yugioh passcode) or a set-code +
 * collector-number pair (mtg `tle-246`), then title-case the rest.
 *
 * Deliberately conservative — if nothing is left after stripping, fall back to
 * the original key rather than invent a name.
 */
export function humaniseMoverKey(key: string): string {
  const parts = key.split('-').filter(Boolean);
  let i = 0;
  // Leading numeric id: yugioh passcode, e.g. `95486586-elemental-hero-core`.
  while (i < parts.length && /^\d+$/.test(parts[i])) i += 1;
  // Set code + collector number, e.g. `tle-246-zuko-avatar-hunter`.
  if (i === 0 && parts.length > 2 && /^[a-z0-9]{2,5}$/.test(parts[0]) && /^\d+$/.test(parts[1])) {
    i = 2;
  }
  const words = parts.slice(i);
  if (!words.length) return key;
  return words
    .map((w, idx) => (idx > 0 && MINOR_WORDS.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(' ');
}

/** Display name — catalog title, or a readable form of the key when uncatalogued. */
export function moverTitle(m: TopMover): string {
  return m.title ?? humaniseMoverKey(moverKey(m));
}
