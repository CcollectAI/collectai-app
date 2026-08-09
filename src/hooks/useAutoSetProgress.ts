/**
 * useAutoSetProgress — fetches auto-computed set completion from
 * the backend /sets/auto-progress endpoint.
 *
 * Uses structured attributes_json from items + catalog to compute
 * completion automatically (no manual set tracking needed).
 */

import { useEffect, useState } from 'react';
import { get } from '@/api/httpClient';
import { logger } from '@/lib/logger';

export type AutoSetEntry = {
  category: string;
  setName: string;
  ownedCount: number;
  catalogTotal: number;
  completionPct: number;
  sampleOwnedTitles: string[];
};

export type UseAutoSetProgressReturn = {
  sets: AutoSetEntry[];
  totalCategories: number;
  totalSets: number;
  loading: boolean;
  error: string | null;
  refetch: () => void;
};

export function useAutoSetProgress(category?: string): UseAutoSetProgressReturn {
  const [sets, setSets] = useState<AutoSetEntry[]>([]);
  const [totalCategories, setTotalCategories] = useState(0);
  const [totalSets, setTotalSets] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchKey, setRefetchKey] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    // Route via httpClient.get so the 5 s fetchWithTimeout, 2 s auth-header
    // race, and retry policy all apply. Previously this hook used bare
    // fetch + bare supabase.auth.getSession(), so a hung token refresh or
    // stalled network left the home-tab spinner spinning forever.
    (async () => {
      try {
        const qs = category ? `?category=${encodeURIComponent(category)}` : '';
        const data = await get<{
          sets?: {
            category: string;
            set_name: string;
            owned_count: number;
            catalog_total: number;
            completion_pct: number;
            sample_owned_titles?: string[];
          }[];
          total_categories?: number;
          total_sets?: number;
        }>(`/sets/auto-progress${qs}`);
        if (!mounted) return;

        const mapped: AutoSetEntry[] = (data.sets ?? []).map((s) => ({
          category: s.category,
          setName: s.set_name,
          ownedCount: s.owned_count,
          catalogTotal: s.catalog_total,
          completionPct: s.completion_pct,
          sampleOwnedTitles: s.sample_owned_titles ?? [],
        }));

        setSets(mapped);
        setTotalCategories(data.total_categories ?? 0);
        setTotalSets(data.total_sets ?? 0);
      } catch (err) {
        logger.error('[useAutoSetProgress] fetch failed:', err);
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to fetch');
          setSets([]);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    return () => { mounted = false; };
  }, [category, refetchKey]);

  return {
    sets,
    totalCategories,
    totalSets,
    loading,
    error,
    refetch: () => setRefetchKey((k) => k + 1),
  };
}
