/**
 * The deal screen's "Why it's a match" lines, from the server's structured
 * policy checks (policy_engine `checks`, stored as mandate_deals.policy_checks).
 *
 * The screen used to print the engine's audit strings verbatim ("total €28.13
 * (price €5.63 + shipping €22.50) <= max €30.0") — and the €22.50 was our own
 * regional GUESS, shown as the listing's shipping (2026-09-24). An estimated
 * shipping cost is now a range the member is told to check, never a number
 * added to the price.
 */
import { formatPrice } from '@/lib/format';
import type { PolicyCheck } from '@/data/types';

type TFn = (key: string, opts?: Record<string, unknown>) => string;

// Checks arrive with snake_case numbers from the server and camelCase after
// camelizeDeep; read both so an older response cannot blank a line.
const num = (c: PolicyCheck, camel: keyof PolicyCheck, snake: string): number | null => {
  const v = (c as Record<string, unknown>)[camel as string] ?? (c as Record<string, unknown>)[snake];
  return typeof v === 'number' ? v : null;
};

export function policyCheckLine(c: PolicyCheck, t: TFn): string | null {
  switch (c.code) {
    case 'price': {
      const max = formatPrice(num(c, 'max', 'max') ?? 0);
      return c.ok
        ? t('purchase.check_price_ok', { max, defaultValue: 'Within your {{max}} limit' })
        : t('purchase.check_price_fail', { max, defaultValue: 'Over your {{max}} limit' });
    }
    case 'budget':
      return c.ok
        ? t('purchase.check_budget_ok', { remaining: formatPrice(num(c, 'remaining', 'remaining') ?? 0), defaultValue: '{{remaining}} left in your total budget' })
        : t('purchase.check_budget_fail', { defaultValue: 'Over your total budget' });
    case 'trust':
      return c.ok
        ? t('purchase.check_trust_ok', { defaultValue: 'Seller and listing meet your trust setting' })
        : t('purchase.check_trust_fail', { defaultValue: 'Below your trust setting' });
    case 'source':
      return c.ok
        ? t('purchase.check_source_ok', { defaultValue: 'From a marketplace you chose' })
        : t('purchase.check_source_fail', { defaultValue: 'Not from a marketplace you chose' });
    case 'keywords':
      return c.ok
        ? t('purchase.check_keywords_ok', { defaultValue: 'None of the words you excluded' })
        : t('purchase.check_keywords_fail', { defaultValue: 'Contains a word you excluded' });
    case 'card':
      return c.ok
        ? t('purchase.check_card_ok', { number: c.number ?? '', defaultValue: 'The card you want (#{{number}})' })
        : t('purchase.check_card_fail', { number: c.number ?? '', defaultValue: 'A different card, not #{{number}}' });
    case 'expired':
      return t('purchase.check_expired', { defaultValue: 'Your search has expired' });
    case 'region':
      return t('purchase.check_region', { defaultValue: "Doesn't ship to your region" });
    default:
      return null;
  }
}

export function shippingLine(c: PolicyCheck, t: TFn): string | null {
  const estimated = Boolean(c.shippingEstimated ?? (c as Record<string, unknown>).shipping_estimated);
  if (estimated) {
    const lo = num(c, 'shippingMin', 'shipping_min');
    const hi = num(c, 'shippingMax', 'shipping_max');
    return lo != null && hi != null
      ? t('purchase.shipping_estimated_range', { min: formatPrice(lo), max: formatPrice(hi), defaultValue: 'Shipping not stated — usually {{min}}–{{max}} to you. Check the listing.' })
      : t('purchase.shipping_estimated', { defaultValue: 'Shipping not stated — check the listing.' });
  }
  const ship = num(c, 'shipping', 'shipping');
  if (ship == null || ship <= 0) return null;
  return t('purchase.shipping_stated', { amount: formatPrice(ship), defaultValue: 'Plus {{amount}} shipping' });
}

