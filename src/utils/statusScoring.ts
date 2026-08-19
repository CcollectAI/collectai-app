export type Tier = 'Diamond' | 'Gold' | 'Silver';

export interface BaseItem {
  id?: string | number;
  name?: string | null;
  title?: string | null;
  category?: string | null;
  value?: number | null;

  // Optional collection metadata
  collection?: string | null;
  collection_name?: string | null;
  set_code?: string | null;
  set_size?: number | null;

  // Optional rarity signal (0–1 or 0–100; treated as 0–1 if <= 1)
  rarity_score?: number | null;
}

export type CollectionStatusInput = BaseItem;

export interface CollectionStatusScore {
  key: string;                 // collection key, e.g. "Pokémon – Base Set"
  category: string;
  itemCount: number;
  ownedCount: number;
  /** From `sets.total_items`. **null when we have no catalogue row for this
   *  set** — callers must branch rather than treat it as 0 or as owned. */
  expectedCount: number | null;
  /** 0–1, or **null** when `expectedCount` is unknown. */
  completenessRatio: number | null;
  rarityScore: number;         // 0–1 (normalized)
  valueTotal: number;
  points: number;              // final score for leaderboard
  tier: Tier;
}

/**
 * Derive a stable key for a "collection".
 * Prefers explicit collection/set fields, falls back to category.
 */
function collectionKey(item: CollectionStatusInput): string {
  const base =
    item.collection ??
    item.collection_name ??
    item.set_code ??
    item.category ??
    'Unknown';

  return base;
}

/**
 * WHY THERE ARE NO SET-SIZE HINTS HERE ANY MORE (2026-08-15)
 * ---------------------------------------------------------
 * There used to be two tables of invented sizes — `EXPECTED_SET_SIZE_HINTS`
 * ('Pokémon – Base Set': 15) and `CATEGORY_DEFAULT_SET_SIZE` ({ Pokemon: 15,
 * Lorcana: 12, … }) — and a final fallback of "expected = however many you
 * own". Three things were wrong with that, and together they made
 * app/sets-to-complete.tsx render nothing at all for every account:
 *
 *   1. Both tables were keyed on DISPLAY names while `items.category` holds
 *      SLUGS ('pokemon', 'lorcana'), so no lookup ever hit
 *      (learning_join_vocabulary_slug_vs_display_name).
 *   2. The fallback therefore always won, making expected === owned, so every
 *      set computed as exactly 100% complete — and the screen's 0.4..0.95 band
 *      filtered all of them out.
 *   3. Even had the keys matched, 15 is not the size of Base Set (it is 102).
 *      A guessed denominator produces a confident, wrong percentage, which is
 *      worse than no percentage.
 *
 * The size now comes from `sets.total_items` via `/portfolio/items`, and when
 * we do not have it, `expectedCount` is **null** rather than a guess. Callers
 * must branch on that: a set of unknown size is not a set of size zero.
 */

/**
 * Simple rarity weights by category if no explicit rarity_score is present.
 * Keyed on SLUGS, matching `items.category` — these were display names, so
 * every lookup missed and every category silently scored the 0.5 fallback.
 */
const CATEGORY_RARITY_WEIGHT: Record<string, number> = {
  pokemon: 0.8,
  mtg: 0.85,
  lorcana: 0.75,
  yugioh: 0.8,
  warhammer: 0.7,
  gunpla: 0.7,
  designer_toys: 0.9,
};

/** A score whose set size we actually know, so a percentage can be shown. */
export type SizedCollectionScore = CollectionStatusScore & {
  expectedCount: number;
  completenessRatio: number;
};

/**
 * Narrowing guard: do we know how big this set is?
 *
 * Use this rather than `?? 0` at each call site. Defaulting a null
 * completeness to 0 turns "we have no catalogue row for this set" into "you
 * own none of it", which is a claim about the member's collection that we
 * cannot support — and it would put every uncatalogued pile into the
 * "Getting started" bucket of app/sets-to-complete.tsx.
 */
export function hasKnownSetSize(s: CollectionStatusScore): s is SizedCollectionScore {
  return s.expectedCount !== null && s.completenessRatio !== null;
}

const EPS = 1e-6;

function normalize01(value: number, min: number, max: number): number {
  if (max <= min + EPS) return 0;
  const clamped = Math.max(min, Math.min(max, value));
  return (clamped - min) / (max - min);
}

/**
 * Normalize rarity_score into 0–1 if caller passed 0–100.
 */
function normalizeRarityScore(raw: number | null | undefined, fallback: number): number {
  if (raw == null || Number.isNaN(raw)) return fallback;
  if (raw > 1) return Math.max(0, Math.min(1, raw / 100));
  return Math.max(0, Math.min(1, raw));
}

/**
 * Compute per-collection completeness + rarity + value based points.
 * This is intentionally client-side only and does NOT hit Supabase or backend.
 */
export function computeCollectionStatusScores(
  items: CollectionStatusInput[],
): CollectionStatusScore[] {
  if (!items.length) return [];

  // Group by collection key
  const byKey: Record<
    string,
    {
      category: string;
      items: CollectionStatusInput[];
      totalValue: number;
    }
  > = {};

  for (const item of items) {
    const key = collectionKey(item);
    if (!byKey[key]) {
      byKey[key] = {
        category: item.category ?? 'Unknown',
        items: [],
        totalValue: 0,
      };
    }
    byKey[key].items.push(item);
    const numericValue = Number(item.value ?? 0);
    if (!Number.isNaN(numericValue)) {
      byKey[key].totalValue += numericValue;
    }
  }

  // Compute global stats for normalization
  let minRarity = Number.POSITIVE_INFINITY;
  let maxRarity = Number.NEGATIVE_INFINITY;
  let minValue = Number.POSITIVE_INFINITY;
  let maxValue = Number.NEGATIVE_INFINITY;

  const rarityPerKey: Record<string, number> = {};
  const valuePerKey: Record<string, number> = {};

  for (const [key, group] of Object.entries(byKey)) {
    const { items: groupItems, category } = group;

    let raritySum = 0;
    let rarityCount = 0;

    for (const item of groupItems) {
      const explicit = item.rarity_score;
      const categoryWeight = CATEGORY_RARITY_WEIGHT[category] ?? 0.5;

      const rarity = normalizeRarityScore(explicit ?? null, categoryWeight);

      raritySum += rarity;
      rarityCount += 1;
    }

    const avgRarity = rarityCount ? raritySum / rarityCount : 0.5;
    rarityPerKey[key] = avgRarity;
    valuePerKey[key] = group.totalValue;

    minRarity = Math.min(minRarity, avgRarity);
    maxRarity = Math.max(maxRarity, avgRarity);
    minValue = Math.min(minValue, group.totalValue);
    maxValue = Math.max(maxValue, group.totalValue);
  }

  if (!Number.isFinite(minRarity)) {
    minRarity = 0;
    maxRarity = 1;
  }
  if (!Number.isFinite(minValue)) {
    minValue = 0;
    maxValue = 1;
  }

  const scores: CollectionStatusScore[] = [];

  for (const [key, group] of Object.entries(byKey)) {
    const { items: groupItems, category, totalValue } = group;

    const ownedCount = groupItems.length;

    // The catalogue's number, or nothing. `set_size` arrives from
    // `sets.total_items`; an item whose set we hold no catalogue row for sends
    // null, and a group of only those has no known size.
    const maxSetSizeFromItems = groupItems.reduce(
      (acc, item) =>
        item.set_size != null
          ? Math.max(acc, item.set_size)
          : acc,
      0,
    );

    const expectedCount: number | null =
      maxSetSizeFromItems > 0 ? maxSetSizeFromItems : null;

    // null, not 0. "We do not know how complete this is" and "this is 0%
    // complete" are different answers and must render differently
    // (learning_empty_answer_rendered_as_zero).
    const completenessRatio: number | null =
      expectedCount === null ? null : Math.min(1, ownedCount / expectedCount);

    const rarityRaw = rarityPerKey[key] ?? 0.5;
    const rarityNorm = normalize01(rarityRaw, minRarity, maxRarity);

    const valueNorm = normalize01(totalValue, minValue, maxValue);

    // Weighting:
    // completeness is king, then rarity, then value.
    //
    // An unknown completeness scores 0 on that axis rather than being treated
    // as complete. It used to be the reverse — unknown size meant expected ===
    // owned meant ratio 1.0 — so every uncatalogued pile collected the full 60
    // points and outranked genuinely finished sets.
    const points =
      (completenessRatio ?? 0) * 60 +
      rarityNorm * 25 +
      valueNorm * 15;

    scores.push({
      key,
      category,
      itemCount: ownedCount,
      ownedCount,
      expectedCount,
      completenessRatio,
      rarityScore: rarityNorm,
      valueTotal: totalValue,
      points,
      tier: tierForPoints(points),
    });
  }

  // Sort descending for leaderboard
  scores.sort((a, b) => b.points - a.points);

  return scores;
}

/**
 * Tier mapping:
 * - Diamond: top 10% or points >= 75
 * - Gold: next 30% or points >= 50
 * - Silver: everyone else
 */
export function tierForPoints(points: number): Tier {
  if (points >= 75) return 'Diamond';
  if (points >= 50) return 'Gold';
  return 'Silver';
}

/**
 * Compute an overall tier for a user given all their collection scores.
 * Aggregates total points and normalizes by collection count.
 */
export function computeOverallTier(
  scores: CollectionStatusScore[],
): { tier: Tier; avgPoints: number } {
  if (!scores.length) {
    return { tier: 'Silver', avgPoints: 0 };
  }
  const total = scores.reduce((sum, s) => sum + s.points, 0);
  const avg = total / scores.length;
  return { tier: tierForPoints(avg), avgPoints: avg };
}
