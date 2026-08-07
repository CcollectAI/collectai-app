/**
 * The currency symbol always leads. One convention, app-wide.
 *
 * This existed as an intention and not as a guarantee. `CURRENCY_LOCALE` picked
 * nl-NL specifically so EUR rendered "€ 5", but BOTH money formatters accepted
 * a caller-supplied locale that overrode it — so a screen calling
 * `formatPrice(x, settings.currency, settings.numberLocale)` rendered "38 €"
 * while Portfolio rendered "€ 0". Same currency, same build, two conventions,
 * decided by which arguments a call site happened to pass.
 *
 * Found by looking at the simulator, not by any test — both spellings are valid
 * `Intl` output, so nothing was ever "wrong" enough to fail.
 */
import { formatPrice, fmtCurrency, getCurrencySymbol } from '@/lib/format';
import type { Currency, NumberLocale } from '@/lib/settings';

const CURRENCIES: Currency[] = ['EUR', 'USD', 'GBP', 'JPY', 'KRW', 'AUD', 'CAD'];
// Deliberately includes de-DE and ja-JP, which put the symbol AFTER the number
// (or in a different spot) under `style: 'currency'`. They are exactly the
// locales that produced the inconsistency.
const LOCALES: NumberLocale[] = ['nl-NL', 'en-US', 'de-DE', 'ja-JP'];

describe('currency symbol position', () => {
  it('leads for every currency, whatever locale the caller passes', () => {
    const offenders: string[] = [];
    for (const c of CURRENCIES) {
      for (const l of LOCALES) {
        const out = formatPrice(1234.5, c, l);
        if (!out.startsWith(getCurrencySymbol(c))) offenders.push(`${c}/${l} -> ${out}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it('leads when no locale is passed at all', () => {
    for (const c of CURRENCIES) {
      expect(formatPrice(42, c).startsWith(getCurrencySymbol(c))).toBe(true);
    }
  });

  it('renders the euro in front, which is what the screens show', () => {
    // The exact strings from the marketplace screens, previously "38 €"/"42 €".
    expect(formatPrice(38, 'EUR', 'de-DE')).toBe('€38');
    expect(formatPrice(42.5, 'EUR', 'nl-NL')).toBe('€43');
  });

  it('keeps the caller locale for grouping — only the symbol moved', () => {
    // nl-NL groups with a dot, en-US with a comma. Losing that would be a
    // regression of its own; the fix was meant to move the symbol, nothing else.
    expect(formatPrice(1234, 'EUR', 'nl-NL')).toBe('€1.234');
    expect(formatPrice(1234, 'EUR', 'en-US')).toBe('€1,234');
  });

  it('fmtCurrency agrees with formatPrice', () => {
    // Two formatters that disagree is the bug this file exists for.
    const s = { currency: 'EUR' as Currency, numberLocale: 'de-DE' as NumberLocale, fxRates: {} };
    expect(fmtCurrency(38, s)).toBe(formatPrice(38, 'EUR', 'de-DE'));
  });

  it('still renders a dash for a missing amount rather than a bare symbol', () => {
    expect(formatPrice(null)).toBe('—');
    expect(formatPrice(undefined)).toBe('—');
    expect(formatPrice(Number.NaN)).toBe('—');
  });

  it('renders zero as a real zero, not as unpriced', () => {
    // An aggregate of zero genuinely is zero — see the note on isUnpriced.
    expect(formatPrice(0, 'EUR')).toBe('€0');
  });
});
