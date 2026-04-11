/**
 * useInterstitial Hook
 *
 * Manages interstitial ad logic with throttling:
 * - Cooldown timer (min 3 minutes between shows)
 * - Action counter (show every N scans/saves)
 * - Session cap (max N per session)
 *
 * Usage:
 *   const { recordAction, tryShow } = useInterstitial('post_scan');
 *   // After a scan completes:
 *   recordAction();
 *   await tryShow(); // only shows if throttle rules allow
 */

import { useRef, useCallback } from 'react';
import { getAdProvider } from './provider';
import { AD_PLACEMENTS, AD_THROTTLE } from './config';
import { useAds } from './useAds';

export interface UseInterstitialReturn {
  /** Record a user action (scan, save, etc.) toward the next interstitial */
  recordAction: () => void;
  /** Try to show an interstitial. Returns true if shown. */
  tryShow: () => Promise<boolean>;
  /** Whether an interstitial is ready to show */
  isReady: boolean;
}

export function useInterstitial(placement: string = 'scan_interstitial'): UseInterstitialReturn {
  const { showAds } = useAds();
  const actionCount = useRef(0);
  const sessionShowCount = useRef(0);
  const lastShownAt = useRef(0);

  const config = AD_PLACEMENTS[placement];
  const unitId = config?.unitId ?? '';

  const recordAction = useCallback(() => {
    actionCount.current += 1;
  }, []);

  const tryShow = useCallback(async (): Promise<boolean> => {
    if (!showAds || !unitId) return false;

    const provider = getAdProvider();

    // Throttle: session cap
    if (sessionShowCount.current >= AD_THROTTLE.INTERSTITIAL_MAX_PER_SESSION) {
      return false;
    }

    // Throttle: cooldown
    const elapsed = (Date.now() - lastShownAt.current) / 1000;
    if (lastShownAt.current > 0 && elapsed < AD_THROTTLE.INTERSTITIAL_COOLDOWN_SEC) {
      return false;
    }

    // Throttle: action counter
    if (actionCount.current < AD_THROTTLE.INTERSTITIAL_EVERY_N_ACTIONS) {
      return false;
    }

    // Try to load if not ready
    if (!provider.isInterstitialReady(unitId)) {
      await provider.loadInterstitial(unitId);
    }

    // Show
    if (!provider.isInterstitialReady(unitId)) {
      return false;
    }

    const shown = await provider.showInterstitial(unitId);
    if (shown) {
      actionCount.current = 0;
      sessionShowCount.current += 1;
      lastShownAt.current = Date.now();
    }
    return shown;
  }, [showAds, unitId]);

  const isReady = showAds && getAdProvider().isInterstitialReady(unitId);

  return { recordAction, tryShow, isReady };
}
