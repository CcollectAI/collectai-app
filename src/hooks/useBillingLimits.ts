import { useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getBillingStatus, type BillingStatus } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';
import {
  addCustomerInfoUpdateListener,
  getCustomerInfo,
  isPurchasesAvailable,
  planFromCustomerInfo,
} from '@/lib/purchases';

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

// Beta-unlock mode — distinct from FORCE_PLAN. When set, every user gets Pro
// limits and the subscription UI advertises beta access instead of paid plans.
// Flip with EXPO_PUBLIC_BETA_UNLOCK_ALL=true in EAS env. Off-switch is a single
// env var change + rebuild — no code edits needed when monetisation goes live.
export const BETA_UNLOCK_ALL = (
  (typeof process !== 'undefined' && (process as { env?: Record<string, string | undefined> }).env?.EXPO_PUBLIC_BETA_UNLOCK_ALL) || ''
).toLowerCase() === 'true';

function getWebLocalStorageOverride(): string {
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      return (window.localStorage.getItem('COLLECTAI_FORCE_PLAN') || '').toLowerCase();
    } catch (e) {
      logger.error('[silent-catch] useBillingLimits.ts:37:', e);
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
  // Beta-unlock short-circuit. Pro limits + 'pro' tier for every install, no
  // RevenueCat / BE calls. Distinct from FORCE_PLAN so beta builds can ship
  // without inheriting the dev-override semantics or storage lookups.
  const initialForced = resolveForced(ENV_FORCE_PLAN, '', getWebLocalStorageOverride());
  const [plan, setPlan] = useState<BillingStatus['plan']>(
    BETA_UNLOCK_ALL ? 'pro' : (initialForced ?? 'free'),
  );
  const [limits, setLimits] = useState<BillingStatus['limits']>(
    BETA_UNLOCK_ALL ? FORCED_LIMITS.pro : (initialForced ? FORCED_LIMITS[initialForced] : DEFAULT_LIMITS),
  );
  const [loading, setLoading] = useState(BETA_UNLOCK_ALL ? false : !initialForced);
  const [isForced, setIsForced] = useState(Boolean(initialForced));

  useEffect(() => {
    if (BETA_UNLOCK_ALL) return; // beta = no RevenueCat / BE listeners
    let mounted = true;

    // RevenueCat is the source of truth for plan tier on iOS/Android.
    // We subscribe to live entitlement updates and fall back to the BE
    // billing endpoint when RevenueCat is unconfigured (web, dev without keys).
    const unsubscribe = addCustomerInfoUpdateListener((info) => {
      if (!mounted) return;
      const rcPlan = planFromCustomerInfo(info);
      if (rcPlan === 'free') return; // don't downgrade FE if BE says otherwise
      setPlan(rcPlan);
      setLimits(FORCED_LIMITS[rcPlan]);
      setLoading(false);
      setIsForced(false);
    });

    // Check AsyncStorage for a runtime override (native path).
    AsyncStorage.getItem(FORCE_PLAN_KEY)
      .then(async (stored) => {
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

        // RevenueCat customer info first — instant + offline-friendly.
        if (isPurchasesAvailable()) {
          const info = await getCustomerInfo();
          if (!mounted) return;
          const rcPlan = planFromCustomerInfo(info);
          if (rcPlan !== 'free') {
            setPlan(rcPlan);
            setLimits(FORCED_LIMITS[rcPlan]);
            setLoading(false);
            return;
          }
          // RevenueCat says free — still hit BE in case the webhook
          // hasn't fired yet (rare race), or the user paid via a path
          // we don't yet recognize.
        }

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

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  return { plan, limits, loading, isForced, isBetaUnlocked: BETA_UNLOCK_ALL };
}
