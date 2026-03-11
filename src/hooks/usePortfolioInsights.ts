/**
 * usePortfolioInsights Hook
 * Computes portfolio insights from real item data and portfolio summary.
 */

import { useState, useEffect, useCallback } from 'react';
import { PortfolioInsights, ItemMover } from '@/types/insights';
import { featureFlags } from '@/config/featureFlags';
import { dataProvider } from '@/data';

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
      const [items, summary] = await Promise.all([
        dataProvider.listItems({ limit: 50 }),  // Top items for movers calculation
        dataProvider.getPortfolioSummary(),
      ]);

      const totalValue = items.reduce((sum, item) => sum + (item.price || 0), 0);
      const percentChange = summary.deltaPct ?? 0;
      const valueChange = totalValue > 0 ? totalValue * (percentChange / 100) : 0;

      // Compute movers from items that have priceBand data
      const movers: ItemMover[] = items
        .filter((item) => item.priceBand && item.priceBand.q50 > 0)
        .map((item) => {
          const median = item.priceBand!.q50;
          const absoluteChange = item.price - median;
          const pctChange = median > 0 ? (absoluteChange / median) * 100 : 0;
          return {
            itemId: item.id,
            name: item.name,
            category: item.category,
            currentValue: item.price,
            previousValue: median,
            absoluteChange,
            percentChange: Math.round(pctChange * 100) / 100,
            imageUrl: item.imageUrl,
          };
        });

      const topGainers = movers
        .filter((m) => m.absoluteChange > 0)
        .sort((a, b) => b.percentChange - a.percentChange)
        .slice(0, 5);

      const topLosers = movers
        .filter((m) => m.absoluteChange < 0)
        .sort((a, b) => a.percentChange - b.percentChange)
        .slice(0, 5);

      const priceDropCount = topLosers.length;

      setInsights({
        totalValue,
        valueChange: Math.round(valueChange * 100) / 100,
        percentChange: Math.round(percentChange * 100) / 100,
        period,
        topGainers,
        topLosers,
        watchlistSummary: {
          totalItems: items.length,
          belowTargetCount: items.filter(
            (i) => i.priceBand && i.price < i.priceBand.q10
          ).length,
          priceDropCount,
          newListingsCount: 0,
        },
        calculatedAt: new Date().toISOString(),
      });
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
