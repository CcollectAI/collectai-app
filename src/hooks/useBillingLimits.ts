import { useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getBillingStatus, type BillingStatus } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';

// Dev override — two ways to flip to a paid tier without real billing:
//   1. EXPO_PUBLIC_FORCE_PLAN=pro|premium in .env (needs Metro restart)
//   2. AsyncStorage key @collectai/force_plan = 'pro'|'premium' (no restart)
//      On web this also honours localStorage['COLLECTAI_FORCE_PLAN'] so you
//      can flip from DevTools: `localStorage.setItem('COLLECTAI_FORCE_PLAN','pro')`
// Added 2026-04-19 after the analytics paywall was blocking preview with no
// accessible way through in web dev mode.
const FORCE_PLAN_KEY = '@collectai/force_plan';

const ENV_FORCE_PLAN = (
  (typeof process !== 'undefined' && (process as { env?: Record<string, string | undefined> }).env?.EXPO_PUBLIC_FORCE_PLAN) || ''
).toLowerCase();

function getWebLocalStorageOverride(): string {
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      return (window.localStorage.getItem('COLLECTAI_FORCE_PLAN') || '').toLowerCase();
    } catch {
      return '';
    }
  }
  return '';
}

const DEFAULT_LIMITS: BillingStatus['limits'] = {
  max_mandates: 3,
  deal_discovery: false,
  dossier_pdf: false,
  advanced_analytics: false,
  condition_grading: false,
  set_completion: false,
  show_ads: true,
};

const FORCED_LIMITS: Record<'pro' | 'premium', BillingStatus['limits']> = {
  pro: {
    max_mandates: 10,
    deal_discovery: true,
    dossier_pdf: true,
    advanced_analytics: true,
    condition_grading: true,
    set_completion: true,
    show_ads: false,
  },
  premium: {
    max_mandates: 50,
    deal_discovery: true,
    dossier_pdf: true,
    advanced_analytics: true,
    condition_grading: true,
    set_completion: true,
    show_ads: false,
  },
};

/**
 * Fetches the user's billing status and exposes plan + feature limits.
 * Returns safe defaults (free tier) while loading or on error.
 */
function resolveForced(envVal: string, storageVal: string, webVal: string): 'pro' | 'premium' | null {
  for (const v of [storageVal, webVal, envVal]) {
    if (v === 'pro' || v === 'premium') return v;
  }
  return null;
}

export function useBillingLimits() {
  const initialForced = resolveForced(ENV_FORCE_PLAN, '', getWebLocalStorageOverride());
  const [plan, setPlan] = useState<BillingStatus['plan']>(initialForced ?? 'free');
  const [limits, setLimits] = useState<BillingStatus['limits']>(
    initialForced ? FORCED_LIMITS[initialForced] : DEFAULT_LIMITS,
  );
  const [loading, setLoading] = useState(!initialForced);
  const [isForced, setIsForced] = useState(Boolean(initialForced));

  useEffect(() => {
    let mounted = true;

    // Check AsyncStorage for a runtime override (native path).
    AsyncStorage.getItem(FORCE_PLAN_KEY)
      .then((stored) => {
        if (!mounted) return;
        const asyncVal = (stored || '').toLowerCase();
        const forced = resolveForced(ENV_FORCE_PLAN, asyncVal, getWebLocalStorageOverride());
        if (forced) {
          setPlan(forced);
          setLimits(FORCED_LIMITS[forced]);
          setIsForced(true);
          setLoading(false);
          return;
        }
        // No override → do the real billing fetch
        getBillingStatus()
          .then((status) => {
            if (!mounted) return;
            setPlan(status.plan);
            setLimits(status.limits);
          })
          .catch((err) => {
            logger.warn('[useBillingLimits] Failed to fetch billing status:', err);
          })
          .finally(() => {
            if (mounted) setLoading(false);
          });
      })
      .catch(() => {
        // AsyncStorage failed — treat as no override
        if (mounted) setLoading(false);
      });

    return () => { mounted = false; };
  }, []);

  return { plan, limits, loading, isForced };
}
