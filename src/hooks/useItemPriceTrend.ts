/**
 * useItemPriceTrend — manages price trend chart data, range selection, and hover state.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { collectorsApi } from '@/api/collectorsApi';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';

interface PriceTrendData {
  data_points: { date: string; q50: number; q10: number; q90: number }[];
  direction: 'up' | 'down' | 'flat';
  pct_change: number;
  current_q50: number;
  period_days: number;
}

export function useItemPriceTrend(itemId: string | undefined, isDraft: boolean) {
  const { settings } = useSettings();

  const [priceTrendData, setPriceTrendData] = useState<PriceTrendData | null>(null);
  const [priceTrendLoading, setPriceTrendLoading] = useState(false);
  const [priceTrendRange, setPriceTrendRange] = useState(90);
  const [priceTrendVisible, setPriceTrendVisible] = useState(false);
  const [priceTrendHoverValue, setPriceTrendHoverValue] = useState<number | null>(null);
  const [priceTrendHoverDate, setPriceTrendHoverDate] = useState<string | null>(null);

  const fetchPriceTrend = useCallback(async (days: number) => {
    if (!itemId || isDraft) return;
    setPriceTrendLoading(true);
    try {
      const data = await collectorsApi.getItemPriceTrend(itemId, days);
      setPriceTrendData(data);
      setPriceTrendHoverValue(null);
      setPriceTrendHoverDate(null);
    } catch (err) {
      logger.error('[useItemPriceTrend] fetch error:', err);
      setPriceTrendData(null);
    } finally {
      setPriceTrendLoading(false);
    }
  }, [itemId, isDraft]);

  useEffect(() => {
    if (priceTrendVisible && !priceTrendData && !priceTrendLoading) {
      fetchPriceTrend(priceTrendRange);
    }
  }, [priceTrendVisible, priceTrendData, priceTrendLoading, priceTrendRange, fetchPriceTrend]);

  const handleRangeChange = useCallback((days: number) => {
    setPriceTrendRange(days);
    fetchPriceTrend(days);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  }, [fetchPriceTrend, settings.hapticsEnabled]);

  const chartData = useMemo(() => {
    if (!priceTrendData?.data_points?.length) return [];
    return priceTrendData.data_points.map((dp) => dp.q50);
  }, [priceTrendData]);

  const handleHover = useCallback((index: number, value: number) => {
    setPriceTrendHoverValue(value);
    if (priceTrendData?.data_points?.[index]) {
      setPriceTrendHoverDate(priceTrendData.data_points[index].date);
    }
  }, [priceTrendData]);

  return {
    priceTrendData,
    priceTrendLoading,
    priceTrendRange,
    priceTrendVisible, setPriceTrendVisible,
    priceTrendHoverValue,
    priceTrendHoverDate,
    handleRangeChange,
    chartData,
    handleHover,
  };
}
