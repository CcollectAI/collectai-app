/**
 * Condition, per category — one resolver for reading, one map for writing.
 *
 * Deliberately built to mirror the CATEGORY vocabulary in
 * `src/constants/categories.ts` (docs/TAXONOMY.md), because `items.condition`
 * has exactly the same defect and the fix there is already reasoned about:
 * store a slug, render a name, normalise at the single write chokepoint, and
 * never show a raw slug.
 *
 * TWO PROBLEMS, BOTH MEASURED ON PROD 2026-08-31
 *
 * 1. **Two vocabularies in one column.** The scan path writes snake_case
 *    (`app/ml/openai_vision.py`: mint / near_mint / very_good / good / fair /
 *    poor) and the manual picker wrote Title Case (`Mint`, `Near Mint`,
 *    `Excellent`). Both are live: `new_sealed` 10, `near_mint` 8, `mint` 5,
 *    `Sealed` 1, `Mint` 1, `NM` 1, `Good` 1, `Excellent` 1, `very_good` 1,
 *    plus graded `PSA 9` / `BGS 10`. `near_mint` rendered raw on the item card,
 *    which is the one thing docs/TAXONOMY.md says the app never does.
 *    `ListForSaleModal` compares `condition === c` against its own Title Case
 *    list, so a scanned item silently lost its pre-selection.
 *
 * 2. **A TCG vocabulary was applied to all 56 categories.** Mint/Near Mint/
 *    Excellent cannot say SEALED -- so a sealed LEGO set and an opened-but-
 *    perfect one were both "Mint", which is the entire value axis for boxed
 *    collectibles. Same break for spirits (fill level, seal) and vinyl
 *    (Goldmine grades). docs/COLLECTOR_DEMAND.md §7 measured this against the
 *    category: no LEGO tracker records condition or sealed-vs-used at all.
 *    `new_sealed` being the MOST common stored value is the tell -- the need
 *    was already there, with no option offering it.
 *
 * Graded values (`PSA 9`, `BGS 10`) are NOT slugs and pass through untouched.
 */

/** Canonical slugs. Stored in `items.condition`; never rendered directly. */
export const CONDITION_LABELS: Record<string, string> = {
  // Card / general grading
  mint: 'Mint',
  near_mint: 'Near Mint',
  excellent: 'Excellent',
  very_good: 'Very Good',
  good: 'Good',
  fair: 'Fair',
  poor: 'Poor',
  // Boxed collectibles — the axis the old list could not express
  new_sealed: 'New / Sealed',
  opened_complete: 'Opened — Complete',
  opened_incomplete: 'Opened — Incomplete',
  built_displayed: 'Built / Displayed',
  damaged: 'Damaged',
  // Spirits
  sealed_full: 'Sealed — Full',
  sealed_low_fill: 'Sealed — Low Fill',
  opened_bottle: 'Opened',
  // Vinyl (Goldmine)
  vg_plus: 'Very Good Plus (VG+)',
  vg: 'Very Good (VG)',
};

/** Display name -> slug. Includes the legacy spellings found in prod. */
export const CONDITION_NAME_TO_SLUG: Record<string, string> = {
  ...Object.fromEntries(Object.entries(CONDITION_LABELS).map(([slug, name]) => [name, slug])),
  // Legacy / abbreviated spellings that exist in the column today.
  NM: 'near_mint',
  'Near mint': 'near_mint',
  Sealed: 'new_sealed',
  'New/Sealed': 'new_sealed',
  'Brand New': 'new_sealed',
};

/** Which option list a category gets. Absent = the general grading list. */
const BOXED = [
  'new_sealed', 'opened_complete', 'opened_incomplete', 'built_displayed', 'damaged',
] as const;
const CARD = ['mint', 'near_mint', 'excellent', 'good', 'fair', 'poor'] as const;
const SPIRITS = ['sealed_full', 'sealed_low_fill', 'opened_bottle', 'damaged'] as const;
const VINYL = ['mint', 'near_mint', 'vg_plus', 'vg', 'good', 'fair', 'poor'] as const;

const CATEGORY_CONDITIONS: Record<string, readonly string[]> = {
  // Boxed: sealed-vs-opened is the value axis, not surface wear.
  lego: BOXED, funko: BOXED, blind_box: BOXED, action_figures: BOXED,
  gunpla: BOXED, hot_toys: BOXED, plush_collectibles: BOXED, diecast: BOXED,
  scale_models: BOXED, marvel_legends: BOXED, designer_toys: BOXED,
  anime_figures: BOXED, bandai_premium: BOXED, loungefly: BOXED,
  vintage_toys: BOXED, oop_board_games: BOXED, warhammer: BOXED,
  nintendo_merch: BOXED, theme_park: BOXED, pop_fandom: BOXED,
  keycaps: BOXED, kpop_lightsticks: BOXED, kpop_merch: BOXED,
  fragrances: BOXED, jewellery: BOXED, sneakers: BOXED, dnd: BOXED,
  // Spirits: fill level and seal are what a buyer asks about.
  whiskey: SPIRITS,
  // Goldmine, the vinyl standard. NOTE: Goldmine grades SLEEVE and DISC
  // separately and this column is single-valued, so the sleeve grade belongs in
  // notes until there is a second field -- exactly the Discogs complaint in
  // docs/COLLECTOR_DEMAND.md §2, only half-solved here on purpose.
  vinyl_records: VINYL, anime_ost_vinyl: VINYL, city_pop_vinyl: VINYL,
};

/** The condition slugs offered for a category. */
export function conditionOptionsFor(category: string | null | undefined): readonly string[] {
  if (!category) return CARD;
  return CATEGORY_CONDITIONS[category] ?? CARD;
}

/**
 * Resolve a value read straight out of `items.condition`.
 * Unknown values are returned as-is: graded strings (`PSA 9`) and anything a
 * user typed are legitimate and must not be mangled -- the same reasoning as
 * `formatCategoryName` returning title-case for an unregistered slug.
 */
export function formatConditionName(value: string | null | undefined): string {
  if (!value) return '';
  const v = value.trim();
  if (CONDITION_LABELS[v]) return CONDITION_LABELS[v];
  // A bare slug we do not know: title-case it rather than show `some_thing`.
  if (/^[a-z][a-z0-9_]*$/.test(v)) {
    return v.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }
  return v;
}

/**
 * For state that may hold EITHER vocabulary -- seeded from the column (a slug)
 * and written by a picker (a display name). Mirrors `categoryDisplayName`;
 * `formatConditionName` alone is not safe there because it would re-title-case
 * a name the picker just wrote.
 */
export function conditionDisplayName(value: string | null | undefined): string {
  if (!value) return '';
  if (CONDITION_NAME_TO_SLUG[value]) return value; // already a display name
  return formatConditionName(value);
}

/**
 * Normalise on WRITE. Call at the single write chokepoint, never at call sites
 * -- normalising per-caller is what left `updateItem` exposed for categories.
 * Unknown values (graded, user-typed) pass through unchanged.
 */
export function toConditionSlug(value: string | null | undefined): string | null {
  if (value == null) return null;
  const v = value.trim();
  if (!v) return null;
  return CONDITION_NAME_TO_SLUG[v] ?? v;
}

/** True when two condition values mean the same thing across vocabularies. */
export function sameCondition(a: string | null | undefined, b: string | null | undefined): boolean {
  const sa = toConditionSlug(a);
  const sb = toConditionSlug(b);
  return sa != null && sa === sb;
}
