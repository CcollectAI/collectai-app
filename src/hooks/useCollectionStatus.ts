import { useMemo } from 'react';
import {
  CollectionStatusInput,
  CollectionStatusScore,
  computeCollectionStatusScores,
  computeOverallTier,
  Tier,
} from '@/utils/statusScoring';

export interface UseCollectionStatusResult {
  scores: CollectionStatusScore[];
  tier: Tier;
  avgPoints: number;
}

/**
 * Shared hook to convert a raw items list into:
 * - per-collection scores
 * - aggregated overall tier for the user.
 */
export function useCollectionStatus(
  items: CollectionStatusInput[],
): UseCollectionStatusResult {
  const scores = useMemo(
    () => computeCollectionStatusScores(items),
    [items],
  );

  const { tier, avgPoints } = useMemo(
    () => computeOverallTier(scores),
    [scores],
  );

  return { scores, tier, avgPoints };
}
