import { useEffect, useState } from 'react';
import { getBillingStatus, type BillingStatus } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';

// Dev override: when EXPO_PUBLIC_FORCE_PLAN=pro|premium is set, skip the
// backend fetch and unlock all paid features. Lets the dev team see what a
// paid user sees without wiring up a real Stripe subscription. Added
// 2026-04-19 after user couldn't preview Pro views through the paywall.
const FORCE_PLAN = (
  (typeof process !== 'undefined' && (process as { env?: Record<string, string | undefined> }).env?.EXPO_PUBLIC_FORCE_PLAN) || ''
).toLowerCase() as '' | 'free' | 'pro' | 'premium';

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
export function useBillingLimits() {
  const forced = FORCE_PLAN === 'pro' || FORCE_PLAN === 'premium' ? FORCE_PLAN : null;
  const [plan, setPlan] = useState<BillingStatus['plan']>(forced ?? 'free');
  const [limits, setLimits] = useState<BillingStatus['limits']>(
    forced ? FORCED_LIMITS[forced] : DEFAULT_LIMITS,
  );
  const [loading, setLoading] = useState(!forced);

  useEffect(() => {
    if (forced) return; // Skip network when plan is forced via env var
    let mounted = true;
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
    return () => { mounted = false; };
  }, [forced]);

  return { plan, limits, loading };
}
