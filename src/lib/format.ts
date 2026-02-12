import type { Currency, NumberLocale, Settings } from './settings';
import { convertEUR } from './fx';

/** Locale lookup for each currency */
const CURRENCY_LOCALE: Record<Currency, NumberLocale> = {
  EUR: 'de-DE',
  USD: 'en-US',
  JPY: 'ja-JP',
  GBP: 'en-US',
};

/* ------------------------------------------------------------------ */
/*  Intl.NumberFormat cache                                           */
/*  Constructing Intl.NumberFormat is ~2-10 µs per call. Since these  */
/*  formatters are called from 23+ components (often in list contexts */
/*  with 50+ items), we cache instances in a Map keyed by a string   */
/*  derived from (locale, currency, style). With 4 currencies x 4    */
/*  locales the cache is bounded at ~16 entries for currency style    */
/*  plus a handful for plain decimal formatting.                      */
/* ------------------------------------------------------------------ */
const _fmtCache = new Map<string, Intl.NumberFormat>();

function getFormatter(
  locale: string,
  opts: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = `${locale}|${opts.style ?? 'decimal'}|${opts.currency ?? '-'}|${opts.maximumFractionDigits ?? ''}`;
  let fmt = _fmtCache.get(key);
  if (!fmt) {
    fmt = new Intl.NumberFormat(locale, opts);
    _fmtCache.set(key, fmt);
  }
  return fmt;
}

/**
 * Format a EUR amount into the selected currency using Settings.fxRates.
 * Preferred when you have access to the full Settings context.
 */
export function fmtCurrency(amountEUR: number, s: Pick<Settings,'currency'|'numberLocale'|'fxRates'>) {
  const val = convertEUR(amountEUR, s);
  const fmt = getFormatter(s.numberLocale, { style: 'currency', currency: s.currency, maximumFractionDigits: 0 });
  return fmt.format(val);
}

/**
 * Standalone price formatter — use when you already have the amount in the
 * correct currency and just need display formatting.
 *
 * @param amount  - numeric value in the given currency
 * @param currency - ISO currency code (default EUR)
 * @param locale  - explicit locale override (auto-detected from currency if omitted)
 */
export function formatPrice(amount: number | null | undefined, currency: Currency = 'EUR', locale?: NumberLocale): string {
  if (amount == null || !Number.isFinite(amount)) return '—';
  const loc = locale ?? CURRENCY_LOCALE[currency] ?? 'en-US';
  try {
    const fmt = getFormatter(loc, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      // All currencies display 0 decimals in this app (intentional).
      maximumFractionDigits: 0,
    });
    return fmt.format(amount);
  } catch {
    return `${amount.toFixed(0)} ${currency}`;
  }
}

/**
 * Format a plain number (no currency symbol).
 */
export function formatNumber(value: number | null | undefined, locale: NumberLocale = 'de-DE'): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const fmt = getFormatter(locale, { maximumFractionDigits: 0 });
  return fmt.format(value);
}
