/**
 * useAds Hook
 *
 * Central gate for ad visibility. Returns { showAds: false } unless ALL of:
 *   1. FEATURE_ADS flag is true (local kill switch)
 *   2. User is on the free plan (paid users never see ads)
 *   3. Ad provider is initialized (SDK loaded)
 *
 * This hook ensures ads are completely dark until explicitly enabled.
 */

import { useMemo } from 'react';
import { featureFlags } from '@/config/featureFlags';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { getAdProvider } from './provider';

export interface UseAdsReturn {
  /** Whether ads should be shown to this user */
  showAds: boolean;
  /** Current plan (for analytics) */
  plan: string;
  /** Whether billing status is still loading */
  loading: boolean;
}

export function useAds(): UseAdsReturn {
  const { plan, loading } = useBillingLimits();

  const showAds = useMemo(() => {
    // Gate 1: Feature flag must be enabled
    if (!featureFlags.FEATURE_ADS) return false;

    // Gate 2: Only free users see ads
    if (plan !== 'free') return false;

    // Gate 3: Ad provider must be initialized
    if (!getAdProvider().isInitialized()) return false;

    return true;
  }, [plan]);

  return { showAds, plan, loading };
}
