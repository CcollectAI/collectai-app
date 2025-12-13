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
  expectedCount: number;
  completenessRatio: number;   // 0–1
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
 * Heuristic expected set size per key.
 * Extend/override as you add real metadata.
 */
const EXPECTED_SET_SIZE_HINTS: Record<string, number> = {
  'Pokémon – Base Set': 15,
  'MTG – Alpha': 25,
};

const CATEGORY_DEFAULT_SET_SIZE: Record<string, number> = {
  Pokemon: 15,
  'Magic: The Gathering': 20,
  Lorcana: 12,
  Warhammer: 10,
  Gunpla: 8,
  'Designer/Art Toys': 6,
};

/**
 * Simple rarity weights by category if no explicit rarity_score is present.
 */
const CATEGORY_RARITY_WEIGHT: Record<string, number> = {
  Pokemon: 0.8,
  'Magic: The Gathering': 0.85,
  Lorcana: 0.75,
  Warhammer: 0.7,
  Gunpla: 0.7,
  'Designer/Art Toys': 0.9,
};

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

    // Use per-item set_size if present, else hints, else ownedCount.
    const hintedSetSize =
      EXPECTED_SET_SIZE_HINTS[key] ??
      CATEGORY_DEFAULT_SET_SIZE[category] ??
      ownedCount;

    const maxSetSizeFromItems = groupItems.reduce(
      (acc, item) =>
        item.set_size != null
          ? Math.max(acc, item.set_size)
          : acc,
      0,
    );

    const expectedCount =
      maxSetSizeFromItems > 0
        ? maxSetSizeFromItems
        : hintedSetSize;

    const completenessRatio =
      expectedCount > 0
        ? Math.min(1, ownedCount / expectedCount)
        : 0;

    const rarityRaw = rarityPerKey[key] ?? 0.5;
    const rarityNorm = normalize01(rarityRaw, minRarity, maxRarity);

    const valueNorm = normalize01(totalValue, minValue, maxValue);

    // Weighting:
    // completeness is king, then rarity, then value.
    const points =
      completenessRatio * 60 +
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
