/**
 * useValueSummary — manages when to show the Instacart-style value notification.
 *
 * Trigger conditions (max 1x per 7 days):
 * - After every 10th scan
 * - After completing a deal
 * - After adding 25th / 50th / 100th / 250th item
 * - On app open if 7+ days since last shown
 *
 * Stores last-shown timestamp in AsyncStorage.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getValueSummary } from '@/api/collectorsApi';
import type { ValueSummaryData } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';

const STORAGE_KEY = 'collectai_value_summary_last_shown';
const MIN_INTERVAL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const SCAN_MILESTONE_INTERVAL = 10; // Every 10 scans
const ITEM_MILESTONES = [25, 50, 100, 250, 500];

export function useValueSummary() {
  const [data, setData] = useState<ValueSummaryData | null>(null);
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const fetchedRef = useRef(false);

  const dismiss = useCallback(async () => {
    setVisible(false);
    try {
      await AsyncStorage.setItem(STORAGE_KEY, Date.now().toString());
    } catch {
      // Ignore storage errors
    }
  }, []);

  const canShow = useCallback(async (): Promise<boolean> => {
    try {
      const lastShown = await AsyncStorage.getItem(STORAGE_KEY);
      if (!lastShown) return true;
      return Date.now() - parseInt(lastShown, 10) >= MIN_INTERVAL_MS;
    } catch {
      return true;
    }
  }, []);

  const checkAndShow = useCallback(async (trigger: 'periodic' | 'scan_milestone' | 'deal_complete' | 'item_milestone') => {
    if (fetchedRef.current || loading) return;

    const allowed = await canShow();
    if (!allowed) return;

    setLoading(true);
    fetchedRef.current = true;

    try {
      const summary = await getValueSummary();

      // Only show if there's something meaningful to display
      const hasSavings = summary.total_money_saved > 0;
      const hasTime = summary.hours_saved >= 0.5;
      if (!hasSavings && !hasTime) return;

      setData(summary);
      setVisible(true);

      logger.info('[ValueSummary] Shown', { trigger, money: summary.total_money_saved, hours: summary.hours_saved });
    } catch (err) {
      logger.warn('[ValueSummary] Failed to fetch:', err);
    } finally {
      setLoading(false);
    }
  }, [canShow, loading]);

  // Check on mount (periodic trigger)
  useEffect(() => {
    checkAndShow('periodic');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Call after scan completion with total scan count.
   */
  const onScanComplete = useCallback((totalScans: number) => {
    if (totalScans > 0 && totalScans % SCAN_MILESTONE_INTERVAL === 0) {
      checkAndShow('scan_milestone');
    }
  }, [checkAndShow]);

  /**
   * Call after deal completion.
   */
  const onDealComplete = useCallback(() => {
    checkAndShow('deal_complete');
  }, [checkAndShow]);

  /**
   * Call after adding an item with the new total count.
   */
  const onItemAdded = useCallback((totalItems: number) => {
    if (ITEM_MILESTONES.includes(totalItems)) {
      checkAndShow('item_milestone');
    }
  }, [checkAndShow]);

  return {
    data,
    visible,
    dismiss,
    onScanComplete,
    onDealComplete,
    onItemAdded,
  };
}
