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

// NOTE: both of these MUST be written as a bare `process.env.EXPO_PUBLIC_X`
// member expression. Expo's babel plugin replaces that exact shape with a
// string literal at build time; it does NOT match a guarded/optional-chained
// read like `(process as {...}).env?.EXPO_PUBLIC_X`. The guarded form compiles
// to a real runtime lookup on `process.env`, which is empty in a release
// bundle — so the flag silently read '' in every built app and beta unlock
// never turned on (set completion stayed gated on TestFlight).
// Proof: in builds/sparrow-ios-internal.ipa the string
// "EXPO_PUBLIC_REVENUECAT_IOS_KEY" is absent (inlined, value baked in) while
// "EXPO_PUBLIC_BETA_UNLOCK_ALL" survives in the Hermes string table.
const ENV_FORCE_PLAN = (process.env.EXPO_PUBLIC_FORCE_PLAN || '').toLowerCase();

// Beta-unlock mode — distinct from FORCE_PLAN. When set, every user gets Pro
// limits and the subscription UI advertises beta access instead of paid plans.
// Flip with EXPO_PUBLIC_BETA_UNLOCK_ALL=true in EAS env. Off-switch is a single
// env var change + rebuild — no code edits needed when monetisation goes live.
export const BETA_UNLOCK_ALL =
  (process.env.EXPO_PUBLIC_BETA_UNLOCK_ALL || '').toLowerCase() === 'true';

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
  // 0, matching PLAN_LIMITS['free'] on the server. Deal discovery is Pro-only
  // and the worker skips free users' mandates entirely, so a free mandate can
  // never produce a deal. This said 3 from before the 2026-07-31 server change
  // until 2026-08-16 — long enough that the paywall copy was written from it
  // and advertised "3 purchase mandates" to people who get none.
  max_mandates: 0,
  max_watchlist_items: 25,
  max_daily_deal_alerts: 1,
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
    max_watchlist_items: null,
    max_daily_deal_alerts: null,
    deal_discovery: true,
    dossier_pdf: true,
    advanced_analytics: true,
    condition_grading: true,
    set_completion: true,
    show_ads: false,
  },
  premium: {
    max_mandates: 50,
    max_watchlist_items: null,
    max_daily_deal_alerts: null,
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
  // DEV ONLY. All three sources are a developer convenience, and all three
  // outlive the session that set them: `@collectai/force_plan` sat in a
  // simulator's AsyncStorage reporting Pro long after the session that wrote
  // it, which read as a paywall leak on the Market tab. In a release build the
  // paywall must come from RevenueCat or the billing endpoint and nowhere else
  // — the same failure eas.json pins EXPO_PUBLIC_BETA_UNLOCK_ALL='false' to
  // prevent, except FORCE_PLAN was pinned by nothing.
  // BETA_UNLOCK_ALL is deliberately NOT gated here: it is a shipped beta mode.
  if (!__DEV__) return null;
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
