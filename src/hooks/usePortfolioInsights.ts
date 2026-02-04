/**
 * usePortfolioInsights Hook
 * Fetches portfolio insights from the backend RPC.
 */

import { useState, useEffect, useCallback } from 'react';
import { PortfolioInsights } from '@/types/insights';
import { featureFlags } from '@/config/featureFlags';

// Mock data for development
const MOCK_INSIGHTS: PortfolioInsights = {
  totalValue: 12450,
  valueChange: 820,
  percentChange: 7.05,
  period: '7d',
  topGainers: [
    {
      itemId: '1',
      name: 'Charizard GX (Alt Art)',
      category: 'Pokémon',
      currentValue: 450,
      previousValue: 380,
      absoluteChange: 70,
      percentChange: 18.4,
    },
    {
      itemId: '2',
      name: 'Funko Pop – Luffy (NYCC)',
      category: 'Funko Pop',
      currentValue: 210,
      previousValue: 190,
      absoluteChange: 20,
      percentChange: 10.5,
    },
  ],
  topLosers: [
    {
      itemId: '3',
      name: 'Hot Wheels RLC Skyline',
      category: 'Diecast',
      currentValue: 140,
      previousValue: 160,
      absoluteChange: -20,
      percentChange: -12.5,
    },
  ],
  watchlistSummary: {
    totalItems: 8,
    belowTargetCount: 3,
    priceDropCount: 2,
    newListingsCount: 1,
  },
  calculatedAt: new Date().toISOString(),
};

export type UsePortfolioInsightsOptions = {
  period?: '7d' | '30d' | '90d';
  enabled?: boolean;
};

export type UsePortfolioInsightsReturn = {
  insights: PortfolioInsights | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
};

export function usePortfolioInsights(
  options: UsePortfolioInsightsOptions = {}
): UsePortfolioInsightsReturn {
  const { period = '7d', enabled = true } = options;
  const [insights, setInsights] = useState<PortfolioInsights | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchInsights = useCallback(async () => {
    if (!enabled || !featureFlags.FEATURE_DATA_INSIGHTS_ALERTS) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // TODO: Replace with actual RPC call
      // const { data, error } = await supabase.rpc('rpc_get_portfolio_insights_v1', { period });

      // Simulate API delay
      await new Promise((r) => setTimeout(r, 500));

      setInsights({ ...MOCK_INSIGHTS, period });
    } catch (e) {
      setError(e instanceof Error ? e : new Error('Failed to fetch insights'));
    } finally {
      setIsLoading(false);
    }
  }, [period, enabled]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  return {
    insights,
    isLoading,
    error,
    refetch: fetchInsights,
  };
}
