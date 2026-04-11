import { useEffect, useState } from 'react';
import { getBillingStatus, type BillingStatus } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';

const DEFAULT_LIMITS: BillingStatus['limits'] = {
  max_mandates: 3,
  deal_discovery: false,
  dossier_pdf: false,
  advanced_analytics: false,
  condition_grading: false,
  set_completion: false,
  show_ads: true,
};

/**
 * Fetches the user's billing status and exposes plan + feature limits.
 * Returns safe defaults (free tier) while loading or on error.
 */
export function useBillingLimits() {
  const [plan, setPlan] = useState<BillingStatus['plan']>('free');
  const [limits, setLimits] = useState<BillingStatus['limits']>(DEFAULT_LIMITS);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
  }, []);

  return { plan, limits, loading };
}
