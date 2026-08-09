/**
 * Duplicate detection utility for item creation.
 *
 * Checks whether a name is too similar to an existing item in the user's
 * collection before saving. Uses bigram overlap for fast fuzzy matching
 * without any external dependencies.
 */

import type { DataProvider } from '@/data/DataProvider';
import { logger } from '@/lib/logger';

// ---------------------------------------------------------------------------
// String similarity (bigram overlap — Dice coefficient)
// ---------------------------------------------------------------------------

/** Extract character bigrams from a string. */
function bigrams(s: string): Map<string, number> {
  const map = new Map<string, number>();
  for (let i = 0; i < s.length - 1; i++) {
    const pair = s.slice(i, i + 2);
    map.set(pair, (map.get(pair) ?? 0) + 1);
  }
  return map;
}

/**
 * Dice coefficient over character bigrams.
 * Returns a value between 0 (completely different) and 1 (identical).
 */
export function similarity(a: string, b: string): number {
  const na = a.toLowerCase().trim();
  const nb = b.toLowerCase().trim();

  if (na === nb) return 1;
  if (na.length < 2 || nb.length < 2) return na === nb ? 1 : 0;

  const bigramsA = bigrams(na);
  const bigramsB = bigrams(nb);

  let intersection = 0;
  for (const [pair, countA] of bigramsA) {
    const countB = bigramsB.get(pair) ?? 0;
    intersection += Math.min(countA, countB);
  }

  const totalA = na.length - 1;
  const totalB = nb.length - 1;

  return (2 * intersection) / (totalA + totalB);
}

// ---------------------------------------------------------------------------
// Duplicate check
// ---------------------------------------------------------------------------

const SIMILARITY_THRESHOLD = 0.85;

export interface DuplicateCheckResult {
  isDuplicate: boolean;
  existingName?: string;
}

/**
 * Check whether an item name is a duplicate (or near-duplicate) of an
 * existing item in the user's collection.
 *
 * @param name      - The new item name to check.
 * @param category  - Optional category slug to narrow the comparison.
 * @param dataProvider - DataProvider instance to fetch existing items.
 */
export async function checkDuplicate(
  name: string,
  category: string | null,
  dataProvider: DataProvider,
): Promise<DuplicateCheckResult> {
  const trimmed = name.trim();
  if (!trimmed) return { isDuplicate: false };

  try {
    const items = await dataProvider.listItems();

    const candidates = category
      ? items.filter((i) => i.category === category)
      : items;

    for (const item of candidates) {
      if (!item.name) continue;

      // Exact match (case-insensitive)
      if (item.name.toLowerCase().trim() === trimmed.toLowerCase()) {
        return { isDuplicate: true, existingName: item.name };
      }

      // Fuzzy match
      if (similarity(trimmed, item.name) >= SIMILARITY_THRESHOLD) {
        return { isDuplicate: true, existingName: item.name };
      }
    }
  } catch (e) {
    logger.error('[silent-fallback] duplicateCheck: item fetch failed, not blocking creation:', e);
    // If fetching items fails, don't block item creation
  }

  return { isDuplicate: false };
}
