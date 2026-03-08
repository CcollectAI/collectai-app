/**
 * Feature tour — context + provider for in-app tooltips.
 *
 * Persists dismissed tips in AsyncStorage so each tip
 * shows only once per user (unless reset from Settings).
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@collectai/feature_tour_dismissed';

export type TipId =
  | 'quickscan_intro'
  | 'items_multi_select'
  | 'watchlist_target_price'
  | 'marketplace_affiliate'
  | 'portfolio_chart_range'
  | 'events_calendar_toggle';

type FeatureTourContextValue = {
  /** Whether a specific tip has been dismissed */
  isDismissed: (tipId: TipId) => boolean;
  /** Dismiss a tip permanently */
  dismiss: (tipId: TipId) => void;
  /** Reset all tips (e.g. from Settings) */
  resetAll: () => void;
  /** Whether the tour state has loaded from storage */
  ready: boolean;
};

const FeatureTourCtx = createContext<FeatureTourContextValue>({
  isDismissed: () => true,
  dismiss: () => {},
  resetAll: () => {},
  ready: false,
});

export function FeatureTourProvider({ children }: { children: React.ReactNode }) {
  const [dismissed, setDismissed] = useState<Set<TipId>>(new Set());
  const [ready, setReady] = useState(false);

  // Load dismissed tips from storage on mount
  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (raw) {
          const arr: TipId[] = JSON.parse(raw);
          setDismissed(new Set(arr));
        }
      })
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  const isDismissed = useCallback(
    (tipId: TipId) => dismissed.has(tipId),
    [dismissed],
  );

  // Persist dismissed tips to storage whenever the set changes
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (dismissed.size > 0) {
      AsyncStorage.setItem(STORAGE_KEY, JSON.stringify([...dismissed])).catch(() => {});
    }
  }, [dismissed]);

  const dismiss = useCallback((tipId: TipId) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(tipId);
      return next;
    });
  }, []);

  const resetAll = useCallback(() => {
    setDismissed(new Set());
    AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
  }, []);

  return (
    <FeatureTourCtx.Provider value={{ isDismissed, dismiss, resetAll, ready }}>
      {children}
    </FeatureTourCtx.Provider>
  );
}

export function useFeatureTour() {
  return useContext(FeatureTourCtx);
}
