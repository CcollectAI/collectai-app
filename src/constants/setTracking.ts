/**
 * Which categories can produce set-completion progress.
 *
 * MEASURED on prod 2026-08-19, not assumed — `category_items.set_name`
 * coverage per category:
 *
 *   yugioh 100.0% · pokemon 100.0% · digimon 100.0% · one_piece_tcg 100.0%
 *   mtg 97.2% · lorcana 71.0%
 *   ...and 0.0% — ZERO rows, not sparse — in all 50 other categories,
 *   every one of whose catalogue rows is `source='seed'`.
 *
 * Completion needs a denominator ("how many are in this set"), so a category
 * with no set names cannot report progress at all. Saying "add more items" to
 * a whiskey or LEGO collector is therefore false instruction: no amount of
 * adding can produce a set. That is what this list exists to prevent.
 *
 * RE-MEASURE before adding a slug — the honest source is the database, not
 * this file:
 *
 *   SELECT category,
 *          round(100.0 * count(*) FILTER (
 *            WHERE NULLIF(btrim(attributes_json->>'set_name'),'') IS NOT NULL
 *          ) / NULLIF(count(*),0), 1) AS pct
 *   FROM public.category_items GROUP BY category ORDER BY pct DESC;
 *
 * LEGO is the likeliest next entry: `REBRICKABLE_API_KEY` is set on the box
 * and `server/pipelines/import_lego.py` already writes 3,410 catalogue rows —
 * but it emits `{set_number, theme, year, num_parts}` and no `set_name`, and
 * "which grouping is actually completable" is an open product question (a
 * theme like Star Wars has thousands of sets; a Collectible Minifigures series
 * has twelve). Do not add `lego` here until the catalogue carries the answer.
 */
export const SET_TRACKING_CATEGORIES: readonly string[] = [
  'pokemon',
  'mtg',
  'yugioh',
  'lorcana',
  'digimon',
  'one_piece_tcg',
];

/** Human-facing list for copy, in the order a collector would recognise. */
export const SET_TRACKING_CATEGORY_LABELS =
  'Pokemon, Magic, Yu-Gi-Oh, Lorcana, Digimon and One Piece';

export function isSetTrackingCategory(category?: string | null): boolean {
  if (!category) return false;
  return SET_TRACKING_CATEGORIES.includes(category.trim().toLowerCase());
}

/**
 * The distinct categories in `items` that set tracking cannot cover.
 *
 * Returns them in first-seen order and de-duplicated, so the caller can name
 * the member's OWN categories back to them ("your lego and whiskey items")
 * rather than reciting a generic list.
 */
export function unsupportedSetCategories(
  items: ReadonlyArray<{ category?: string | null }>,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const it of items) {
    const c = it.category?.trim().toLowerCase();
    if (!c || isSetTrackingCategory(c) || seen.has(c)) continue;
    seen.add(c);
    out.push(c);
  }
  return out;
}
