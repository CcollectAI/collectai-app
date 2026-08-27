/**
 * Sanity filter for marketplace search rows before they are shown to a member.
 *
 * WHY (2026-08-27)
 * ----------------
 * Reported from a TestFlight screenshot of a LEGO item's "Market Prices"
 * section, on the PRO tier:
 *
 *     Site Statistics          €1.620.277.371
 *     crawl4ai
 *
 * A crawl4ai adapter had scraped a page's own statistics counter and filed it
 * as a market price. `useItemMarketplace.loadMarketResults` took whatever the
 * endpoint returned and rendered it verbatim — there was no bound of any kind
 * on the display path. One-point-six BILLION euro, presented as a comparable,
 * on a paid feature.
 *
 * The real fix belongs at the adapter, and this is not a substitute for it.
 * But a member should never be the thing that catches this, so the display
 * path now refuses to render a number it can prove is not a price.
 *
 * WHAT IT DOES *NOT* DO
 * ---------------------
 * No keyword rules. `docs/MARKET_DATA.md` is explicit that keyword filtering on
 * marketplace titles "was measured and it costs all of the yield for none of
 * the precision", and a title blocklist would be exactly that — plus a rule
 * that rejects "Site Statistics" today rejects a legitimately-named product
 * tomorrow. Everything here is arithmetic on the price alone.
 */

/** The bound the server already uses. `valuation_worker._MAX_SANE_PRICE_EUR`
 *  is 20,000,000 and is pinned by `server/tests/test_r50l_hardening.py`, so
 *  the two ends of the pipeline agree on what "not a price" means. */
export const MAX_SANE_PRICE = 20_000_000;

/** How far above the item's OWN valuation a comparable may sit before it is
 *  treated as junk rather than as a wide market.
 *
 *  Deliberately loose. The server's snipe path uses a 0.35x-4x band, but that
 *  exists to decide whether to FIRE AN ALERT; this decides whether to SHOW a
 *  row, and hiding a genuine outlier is a worse failure here than showing a
 *  wide one. 100x still kills a EUR 1.6bn row against a EUR 50 set by four
 *  orders of magnitude. */
export const MAX_MULTIPLE_OF_VALUATION = 100;

export type SanityCheckable = { price?: number | null };

/**
 * Keep only rows that could plausibly be a price.
 *
 * @param hits      rows as returned by the marketplace search
 * @param valuation the item's own value, when known. Undefined/0 means we have
 *                  no reference and only the absolute bound applies — an
 *                  unpriced item must not have its whole comp list emptied.
 */
export function filterImplausibleHits<T extends SanityCheckable>(
  hits: T[],
  valuation?: number | null,
): { kept: T[]; dropped: number } {
  const ref = typeof valuation === "number" && valuation > 0 ? valuation : null;
  const kept = hits.filter((h) => {
    const p = h.price;
    // Not a number, or not a positive one, is not a price. `0` in particular
    // is what an adapter returns when it could not parse the amount.
    if (typeof p !== "number" || !isFinite(p) || p <= 0) return false;
    if (p > MAX_SANE_PRICE) return false;
    if (ref !== null && p > ref * MAX_MULTIPLE_OF_VALUATION) return false;
    return true;
  });
  return { kept, dropped: hits.length - kept.length };
}

// ── Relevance ───────────────────────────────────────────────────────────────

/**
 * Titles that are demonstrably not the item itself.
 *
 * From `_TCG_REJECT_TOKENS` in
 * `server/workers/marketplace_scrape_scheduler.py`, where every entry was added
 * against an OBSERVED false positive rather than guessed.
 *
 * ⚠️ MATCHED ON WORD BOUNDARIES, NOT AS SUBSTRINGS — and that is not a
 * stylistic difference. The server does `tok in lt`, which is safe there
 * because it only ever runs on six TCG categories. Run over EVERY category, as
 * it is here, plain substring matching rejected **7 of 9** real titles in a
 * one-minute audit: `tin` is inside S·tin·g, Con·tin·ental, Tin·tin,
 * Pain·tin·g, Quen·tin and Chris·tin·a. A vinyl collection would have lost most
 * of its comps to a rule written about Pokémon tins.
 *
 * `learning_keyword_filters_need_per_category_false_positive_audit`: read EVERY
 * match, never the total. `__tests__/lib/marketHitSanity.test.ts` pins those
 * nine titles so this cannot regress.
 *
 * `alter`/`altered` were DROPPED from the general list. They mean "altered art"
 * in a TCG context and are a band name ("Alter Bridge") outside it — the one
 * false positive word boundaries do not fix. The token rule still has to pass,
 * so an altered-art listing carrying the full card name is the residual risk,
 * and that is the right way round: a hidden real comp costs less than a wrong
 * one shown as evidence.
 */
const REJECT_TOKENS = [
  "custom", "proxy", "playmat", "sleeve", "sleeves", "token",
  "sticker", "poster", "art print", "hand-painted", "hand painted",
  "digital", "code card", "empty box", "binder",
  "tin", "tins", "bundle", "booster", "pack", "packs", "sealed", "lot of",
  "collection box", "elite trainer", "blister", "display",
];

/** Word-boundary test. `\b` alone is wrong for multi-word entries like
 *  "art print" and "lot of", so the whole phrase is escaped and bounded. */
function containsRejectToken(lower: string): boolean {
  return REJECT_TOKENS.some((tok) => {
    const escaped = tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, "i").test(lower);
  });
}

/**
 * Significant tokens of a title.
 *
 * The server splits on `[^a-z0-9]+` and keeps tokens of length >= 3. That works
 * for "Bayou" and returns NOTHING for
 * "ウッドストック 愛と平和と音楽の3日間" — Japanese has no spaces and no latin
 * letters, so a latin-only tokeniser yields an empty list and
 * `_is_plausible_tcg_listing` then rejects every listing. Porting it unchanged
 * would have emptied the comps on exactly the item that prompted this work.
 *
 * So: latin/digit runs of >= 3, PLUS CJK runs of >= 2 (a two-character
 * compound is already meaningful in Japanese, where three latin letters are
 * not).
 */
export function significantTokens(title: string): string[] {
  if (!title) return [];
  const lower = title.toLowerCase();
  const latin = (lower.match(/[a-z0-9]+/g) ?? []).filter((t) => t.length >= 3);
  const cjk = (lower.match(/[぀-ヿ㐀-䶿一-鿿]{2,}/g) ?? []);
  return [...latin, ...cjk];
}

/**
 * Is this listing plausibly the same item we searched for?
 *
 * Mirrors `_is_plausible_tcg_listing`, minus the TCG category-marker arm (that
 * rule's `accept` table only covers six TCG categories, and this runs for every
 * category). What carries over is the part that does the work: **every
 * significant token of the item's title must appear in the listing's title.**
 *
 * Deliberately conservative, for the reason the server states: the failure
 * modes are not symmetrical. A false negative costs one hidden listing; a false
 * positive puts an unrelated record under a valuation as though it were
 * evidence for it — which is the reported bug.
 */
export function isPlausibleListing(listingTitle: string, itemTitle: string): boolean {
  if (!listingTitle || !itemTitle) return false;
  const lt = listingTitle.toLowerCase();
  if (containsRejectToken(lt)) return false;
  const tokens = significantTokens(itemTitle);
  // Nothing substantial to match on. Claiming relevance from no evidence is
  // what produced the original screenshot, so say "none" instead.
  if (tokens.length === 0) return false;
  return tokens.every((t) => lt.includes(t));
}

export type RelevanceCheckable = SanityCheckable & { title?: string | null };

/**
 * Sanity AND relevance, in the order they should be applied.
 *
 * Returns the two drop counts separately because they mean different things:
 * `droppedImplausiblePrice` is an adapter emitting non-prices, and
 * `droppedIrrelevant` is a search returning other products. Collapsing them
 * would hide which one is happening.
 */
export function filterComps<T extends RelevanceCheckable>(
  hits: T[],
  itemTitle: string,
  valuation?: number | null,
): { kept: T[]; droppedImplausiblePrice: number; droppedIrrelevant: number } {
  const { kept: priced, dropped: droppedImplausiblePrice } =
    filterImplausibleHits(hits, valuation);
  const kept = priced.filter((h) => isPlausibleListing(h.title ?? "", itemTitle));
  return {
    kept,
    droppedImplausiblePrice,
    droppedIrrelevant: priced.length - kept.length,
  };
}
