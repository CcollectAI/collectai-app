/**
 * A price a MEMBER set — an asking price, a bid, shipping — in the viewer's
 * currency. The ONE place the marketplace formats one (2026-10-15).
 *
 * Five screens each wrote `formatPrice(convertCurrency(...))` by hand (listing
 * grid, its share label, listing detail, offers, offer detail). Two rules live
 * here instead of five times:
 *
 * 1. Convert from the SELLER's currency first — a ¥8000 card printed as "€8000"
 *    is the bug every one of those copies carried a comment about.
 * 2. To the cent when it is the member's own number: walked on Android, a
 *    €20 + €2,50 listing read "€23 total incl. shipping" and a €17,50 offer read
 *    "€18". After FX conversion the cents are an estimate, so whole units again.
 */
import { formatPrice } from './format';
import { convertCurrency } from './fx';
import type { CurrencyCode } from '@/data/types';
import type { Settings } from './settings';

export function formatMemberPrice(
  amount: number | null | undefined,
  from: string | null | undefined,
  s: Pick<Settings, 'currency' | 'fxRates'> & { numberLocale?: Settings['numberLocale'] },
): string {
  if (amount == null || !Number.isFinite(amount)) return '—';
  const source = ((from as CurrencyCode) || 'EUR');
  // currency-ok: converted into s.currency on the line below.
  return formatPrice(
    convertCurrency(amount, source, s.currency, s.fxRates),
    s.currency,
    s.numberLocale,
    { exact: source === s.currency },
  );
}
