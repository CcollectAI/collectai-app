/**
 * useAutoSetProgress — fetches auto-computed set completion from
 * the backend /sets/auto-progress endpoint.
 *
 * Uses structured attributes_json from items + catalog to compute
 * completion automatically (no manual set tracking needed).
 */

import { useEffect, useState } from 'react';
import { API_BASE } from '@/api/config';
import { logger } from '@/lib/logger';
import { supabase } from '@/lib/supabase';

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

    (async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token;
        if (!token) {
          if (mounted) {
            setSets([]);
            setLoading(false);
          }
          return;
        }

        const url = new URL(`${API_BASE}/sets/auto-progress`);
        if (category) url.searchParams.set('category', category);

        const resp = await fetch(url.toString(), {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        if (!mounted) return;

        const mapped: AutoSetEntry[] = (data.sets ?? []).map((s: any) => ({
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
        logger.warn('[useAutoSetProgress] fetch failed:', err);
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
