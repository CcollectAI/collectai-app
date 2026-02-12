/* Shared portfolio analytics hook
 *
 * Uses the unified analytics engine (portfolioAnalyticsStore.ts) to expose:
 * - snapshot: full PortfolioSnapshot (pl, series, allocations, items, tierSummary)
 * - series: TimeSeriesPoint[] (value over time, sorted ascending by t)
 * - pl: portfolio P/L summary (start/current/deltaAbs/deltaPct/maxDrawdownPct)
 *
 * This should be used by:
 * - app/(tabs)/portfolio.tsx  (Robinhood-style chart & header card)
 * - app/analytics.tsx         (inventory / investor overview)
 */

import { useEffect, useMemo, useState } from 'react';
import {
  fetchPortfolioSnapshot,
} from '@/store/portfolioAnalyticsStore';
import type {
  PortfolioSnapshot,
  TimeSeriesPoint,
} from '@/analytics/portfolioMetrics';
import { logger } from '@/lib/logger';

type UsePortfolioSeriesState = {
  loading: boolean;
  error: string | null;
  snapshot: PortfolioSnapshot | null;
  series: TimeSeriesPoint[];
  pl: PortfolioSnapshot['pl'] | null;
};

export function usePortfolioSeries(): UsePortfolioSeriesState {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const snap = await fetchPortfolioSnapshot();
        if (!active) return;
        setSnapshot(snap);
      } catch (err: unknown) {
        logger.warn('[usePortfolioSeries] failed to load snapshot', err);
        if (!active) return;
        setError('Could not load portfolio analytics.');
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, []);

  const sortedSeries: TimeSeriesPoint[] = useMemo(() => {
    if (!snapshot?.series?.length) return [];
    return [...snapshot.series].sort(
      (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime(),
    );
  }, [snapshot]);

  const pl = snapshot?.pl ?? null;

  return {
    loading,
    error,
    snapshot,
    series: sortedSeries,
    pl,
  };
}
