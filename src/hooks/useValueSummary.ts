/**
 * useValueSummary — manages when to show the Instacart-style value notification.
 *
 * Trigger conditions (max 1x per 7 days):
 * - After first scan (milestone)
 * - After every 5th scan
 * - After completing a deal
 * - After adding 10th / 25th / 50th / 100th / 250th / 500th item
 * - After a duplicate is prevented
 * - On app open if 7+ days since last shown
 *
 * Stores last-shown timestamp in AsyncStorage.
 */

import { useState, useCallback, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getValueSummary } from '@/api/collectorsApi';
import type { ValueSummaryData } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';

const STORAGE_KEY = 'collectai_value_summary_last_shown';
const MIN_INTERVAL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const SCAN_MILESTONE_INTERVAL = 5; // Every 5 scans
const ITEM_MILESTONES = [10, 25, 50, 100, 250, 500];

export type SavingsTrigger =
  | 'periodic'
  | 'scan_milestone'
  | 'first_scan'
  | 'deal_complete'
  | 'item_milestone'
  | 'duplicate_prevented';

export function useValueSummary() {
  const [data, setData] = useState<ValueSummaryData | null>(null);
  const [visible, setVisible] = useState(false);
  const [trigger, setTrigger] = useState<SavingsTrigger | null>(null);
  const [loading, setLoading] = useState(false);
  const inflightRef = useRef(false);

  const dismiss = useCallback(async () => {
    setVisible(false);
    setTrigger(null);
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

  const checkAndShow = useCallback(async (trig: SavingsTrigger) => {
    if (inflightRef.current || loading || visible) return;

    const allowed = await canShow();
    if (!allowed) return;

    inflightRef.current = true;
    setLoading(true);

    try {
      const summary = await getValueSummary();

      // Only show if there's something meaningful to display
      const hasSavings = summary.total_money_saved > 0;
      const hasTime = summary.hours_saved >= 0.5;
      if (!hasSavings && !hasTime) return;

      setData(summary);
      setTrigger(trig);
      setVisible(true);

      logger.info('[ValueSummary] Shown', { trigger: trig, money: summary.total_money_saved, hours: summary.hours_saved });
    } catch (err) {
      logger.warn('[ValueSummary] Failed to fetch:', err);
    } finally {
      setLoading(false);
      inflightRef.current = false;
    }
  }, [canShow, loading, visible]);

  /**
   * Call after scan completion with total scan count.
   */
  const onScanComplete = useCallback((totalScans: number) => {
    if (totalScans === 1) {
      checkAndShow('first_scan');
    } else if (totalScans > 0 && totalScans % SCAN_MILESTONE_INTERVAL === 0) {
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

  /**
   * Call after a duplicate is prevented (user chose not to add).
   */
  const onDuplicatePrevented = useCallback(() => {
    checkAndShow('duplicate_prevented');
  }, [checkAndShow]);

  return {
    data,
    visible,
    trigger,
    dismiss,
    onScanComplete,
    onDealComplete,
    onItemAdded,
    onDuplicatePrevented,
  };
}
