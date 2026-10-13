/**
 * A free member who hits a plan cap is a sale, not an error.
 *
 * 2026-09-24: the server enforced every free cap with a coded 403
 * (PLAN_LIMIT_WATCHLIST, PLAN_LIMIT_ALERTS, PLAN_REQUIRED), and only the deal
 * screen read the code. The four "add to watchlist" controls turned the 26th
 * watch into "Could not add to watchlist — try again", so a member at the
 * exact moment the upgrade is worth something was told to retry a request
 * that can never succeed, with no road to the paywall.
 *
 * Returns true when it handled the error (the caller then shows nothing).
 */
import { Alert } from 'react-native';
import type { TFunction } from 'i18next';
import { FREE_PLAN_LIMITS } from '@/hooks/useBillingLimits';

const PLAN_CODES = new Set([
  'PLAN_LIMIT_WATCHLIST', 'PLAN_LIMIT_ALERTS', 'PLAN_LIMIT_ITEMS', 'PLAN_REQUIRED',
]);

export function planLimitCode(err: unknown): string | null {
  const e = err as { code?: unknown; message?: unknown } | null;
  const code = e?.code;
  if (typeof code === 'string' && PLAN_CODES.has(code)) return code;
  // The free-plan item cap is a DATABASE trigger (trg_items_free_cap). Through
  // the API it arrives as code PLAN_LIMIT_ITEMS; through a direct supabase-js
  // insert (add-manual) it arrives as Postgres code P0001 with the marker in
  // the message, so match the message too.
  const message = e?.message;
  if (typeof message === 'string' && message.includes('PLAN_LIMIT_ITEMS')) return 'PLAN_LIMIT_ITEMS';
  return null;
}

export function offerProOnPlanLimit(
  err: unknown,
  t: TFunction,
  openPaywall: () => void,
): boolean {
  const code = planLimitCode(err);
  if (!code) return false;
  const watchlist = code === 'PLAN_LIMIT_WATCHLIST';
  const items = code === 'PLAN_LIMIT_ITEMS';
  Alert.alert(
    t(watchlist ? 'billing.limit_watchlist_title'
      : items ? 'billing.limit_items_title' : 'billing.limit_generic_title'),
    watchlist
      ? t('billing.limit_watchlist_body', { count: FREE_PLAN_LIMITS.max_watchlist_items ?? 25 })
      : items
        ? t('billing.limit_items_body', { count: FREE_PLAN_LIMITS.max_items ?? 100 })
        : t('billing.limit_generic_body'),
    [
      { text: t('common.not_now'), style: 'cancel' },
      { text: t('billing.see_pro'), onPress: openPaywall },
    ],
  );
  return true;
}
