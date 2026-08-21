import type { Currency, NumberLocale, Settings } from './settings';
import { convertEUR } from './fx';
import { logger } from '@/lib/logger';

/** Map currency code to its symbol for inline display. */
const CURRENCY_SYMBOLS: Record<Currency, string> = {
  EUR: '€',
  USD: '$',
  GBP: '£',
  JPY: '¥',
  KRW: '₩',
  AUD: 'A$',
  CAD: 'C$',
};

export function getCurrencySymbol(currency: Currency): string {
  return CURRENCY_SYMBOLS[currency] ?? currency;
}

/** Locale lookup for each currency */
/**
 * The number locale that matches the UI LANGUAGE, pushed in by SettingsProvider.
 *
 * Grouping separators are a property of the language you are reading, not of the
 * currency you are reading about. EUR was mapped to `nl-NL` below, so a
 * EUR 184,194 watch rendered as **"€184.194"** to an English reader — which
 * parses as one hundred and eighty-four euros. The same string is correct in
 * Dutch. 148 of the 164 `formatPrice` call sites pass no locale at all, so this
 * was the default path for almost every price in the app, not one screen.
 *
 * Set here rather than threaded through 148 call sites: one chokepoint, and no
 * sweep to get out of date. `null` until the provider mounts, which only
 * affects module-init-time formatting (there is none).
 */
let _activeNumberLocale: NumberLocale | null = null;

/** Called by SettingsProvider whenever the resolved UI language changes. */
export function setActiveNumberLocale(locale: NumberLocale | null): void {
  _activeNumberLocale = locale;
}

/**
 * Kept ONLY as a last-resort fallback for a currency when no UI language is
 * known. It no longer decides symbol placement — `money()` always leads with
 * the symbol — so its sole remaining effect is grouping, which is why EUR must
 * not sit on a Dutch locale here.
 */
const CURRENCY_LOCALE: Record<Currency, NumberLocale> = {
  // Used for NUMBER formatting only — grouping and decimal separators. The
  // currency symbol is no longer positioned by the locale: `money()` below
  // always leads with it. This entry used to be nl-NL specifically to get the
  // euro on the left, which worked until a caller passed its own locale — and
  // once symbol placement moved into money(), the Dutch grouping it dragged
  // along became a bug for every non-Dutch reader (see _activeNumberLocale).
  EUR: 'en-US',
  USD: 'en-US',
  JPY: 'ja-JP',
  GBP: 'en-US',
  KRW: 'ko-KR',
  AUD: 'en-AU',
  CAD: 'en-US',
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
 * The ONE place a money string is assembled: symbol first, always.
 *
 * `Intl.NumberFormat` with `style: 'currency'` puts the symbol wherever the
 * LOCALE says. That made the app contradict itself — CURRENCY_LOCALE above
 * picks nl-NL precisely to get "€ 5", but both money formatters accept a
 * caller-supplied locale that silently overrode it, so screens passing
 * `settings.numberLocale` rendered "38 €" while Portfolio rendered "€ 0".
 * Same currency, same app, two conventions, depending only on which argument a
 * given call site happened to pass.
 *
 * So the symbol is no longer positioned by the locale. The locale still formats
 * the NUMBER (grouping and decimal separators are genuinely locale-specific and
 * a Dutch user should keep "1.234"), and the symbol is prefixed here.
 */
function money(amount: number, currency: Currency, locale: string): string {
  const num = getFormatter(locale, {
    style: 'decimal',
    minimumFractionDigits: 0,
    // All currencies display 0 decimals in this app (intentional).
    maximumFractionDigits: 0,
  }).format(amount);
  return `${getCurrencySymbol(currency)}${num}`;
}

/**
 * Format a EUR amount into the selected currency using Settings.fxRates.
 * Preferred when you have access to the full Settings context.
 */
export function fmtCurrency(amountEUR: number, s: Pick<Settings,'currency'|'numberLocale'|'fxRates'>) {
  const val = convertEUR(amountEUR, s);
  return money(val, s.currency, s.numberLocale);
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
  // Explicit argument wins, then the UI language, then the currency's own
  // fallback. The middle step is what makes the 148 call sites that pass no
  // locale render in the language the user is actually reading.
  const loc = locale ?? _activeNumberLocale ?? CURRENCY_LOCALE[currency] ?? 'en-US';
  try {
    return money(amount, currency, loc);
  } catch (e) {
    logger.error('[silent-catch] format.ts:86:', e);
    // Fallback also leads with the symbol, so a formatter failure does not
    // flip the convention on one screen.
    return `${getCurrencySymbol(currency)}${amount.toFixed(0)}`;
  }
}

/**
 * "We have no price" vs "this is worth nothing" are different facts, and the
 * intake pipeline collapses both to 0 (an ISBN scan with no market comps saves
 * estimated_value = 0). Showing "€ 0" reads as *worthless* when it means
 * *unknown*, so treat a missing-or-zero value as unpriced. No collectible a
 * user bothers to track is genuinely worth 0, so this direction is safe.
 *
 * Lives here (not in a component) because more than one surface renders a
 * per-item value: the detail card AND the collection list row. Two copies of
 * this rule would drift. NOTE: this is a PER-ITEM rule only — an aggregate
 * ("Collection total", "Portfolio total") of zero genuinely is zero and must
 * keep rendering "€ 0".
 */
/**
 * Reworded 2026-08-20 (was "Cannot estimate value"). "Cannot" is a claim about
 * our ability and reads as permanent — the member's reasonable reading is that
 * this item will never carry a value. The truth is narrower: no sold comp has
 * reached this row YET, and for the 40+ categories with no comp source that is
 * a data-coverage fact, not a verdict on the item.
 *
 * "Not yet priced" is also the wording the server side already uses for the
 * same absence at category level (CLAUDE.md, "An unpriced item is not a
 * zero-euro item"), so the app now says one thing about one fact.
 */
export const UNPRICED_LABEL = 'Not yet priced';

/** Coerce a string|number value to a finite number, or undefined. */
export function toPriceNum(value: string | number | undefined | null): number | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!Number.isFinite(num)) return undefined;
  return num;
}

/** True when a per-item value is missing, unparseable, or zero. See UNPRICED_LABEL. */
export function isUnpriced(value: string | number | undefined | null): boolean {
  const n = toPriceNum(value);
  return n === undefined || n === 0;
}

/**
 * Format a plain number (no currency symbol).
 */
export function formatNumber(value: number | null | undefined, locale: NumberLocale = 'de-DE'): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const fmt = getFormatter(locale, { maximumFractionDigits: 0 });
  return fmt.format(value);
}

/**
 * Format a dual-price display: primary (user currency) + secondary (original listing currency).
 *
 * Returns { primary, secondary } where secondary is null if same currency.
 * The secondary string is prefixed with "~" to indicate conversion.
 */
export function formatDualPrice(
  amountEUR: number,
  originalCurrency: Currency | string,
  s: Pick<Settings, 'currency' | 'numberLocale' | 'fxRates'>,
): { primary: string; secondary: string | null } {
  const primary = fmtCurrency(amountEUR, s);

  // If the listing currency matches the user's currency, no secondary needed
  if (originalCurrency === s.currency) {
    return { primary, secondary: null };
  }

  // If the original currency is EUR, format directly
  if (originalCurrency === 'EUR') {
    const origFormatted = formatPrice(amountEUR, 'EUR');
    return { primary, secondary: `~${origFormatted}` };
  }

  // Convert EUR amount to original currency for display
  const origCur = originalCurrency as Currency;
  const origLocale = CURRENCY_LOCALE[origCur] ?? 'en-US';
  const origRate = (s.fxRates as Record<string, number>)?.[origCur] ?? 1;
  const origAmount = amountEUR * origRate;
  const origFormatted = formatPrice(origAmount, origCur, origLocale);
  return { primary, secondary: `~${origFormatted}` };
}

/**
 * Parse a money value a USER typed. Returns null when it isn't a usable number.
 *
 * The app ships in 7 currencies and most of Europe types `12,50`. Every
 * hand-rolled parse of that string has been wrong in one of four ways, all of
 * which produce a plausible NUMBER rather than an error, so nothing catches
 * them:
 *
 *   parseFloat(v.replace(/[^\d.]/g, ''))   "12,50" -> 1250   100x too big
 *   parseFloat(v.replace(/[^\d,]/g, ''))   "12.50" -> 1250   100x too big
 *   parseFloat(v)                          "12,50" -> 12     truncated
 *   keeps both separators, normalises      "1,5"   -> 1      stops at the comma
 *   neither
 *
 * The first shipped in `app/watchlist-builder.tsx` and made every European
 * seller's target price a hundred times too high — a watchlist row that saves
 * fine and can never fire.
 *
 * Use this instead of parsing inline. `npm run check:numbers`
 * (scripts/check-locale-number-parsing.mjs) fails the build on the raw forms.
 *
 * Deliberately NOT locale-aware beyond the separator: guessing whether "1,234"
 * means 1234 or 1.234 from a device locale is a coin flip on a value that
 * decides what someone pays. Thousands separators are stripped, the LAST
 * separator wins as the decimal point, which is what a human means when they
 * type it.
 */
export function parseMoney(value: string | null | undefined): number | null {
  if (typeof value !== 'string') return null;
  const cleaned = value.replace(/[^0-9.,]/g, '');
  if (!cleaned) return null;
  // The last separator is the decimal point; anything before it is grouping.
  const lastSep = Math.max(cleaned.lastIndexOf('.'), cleaned.lastIndexOf(','));
  const normalised =
    lastSep === -1
      ? cleaned
      : cleaned.slice(0, lastSep).replace(/[.,]/g, '') + '.' + cleaned.slice(lastSep + 1);
  const n = parseFloat(normalised);
  return Number.isFinite(n) ? n : null;
}
