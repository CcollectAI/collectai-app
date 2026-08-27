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
