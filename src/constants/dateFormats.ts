/**
 * Centralized date format options.
 * Use with Date.toLocaleDateString() across the app.
 */

/** "Feb 27" — compact for cards and list items */
export const DATE_SHORT: Intl.DateTimeFormatOptions = {
  month: 'short',
  day: 'numeric',
};

/** "Feb 27, 2026" — full date with year */
export const DATE_SHORT_YEAR: Intl.DateTimeFormatOptions = {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
};

/** "February 2026" — month + year for member-since type displays */
export const DATE_MONTH_YEAR: Intl.DateTimeFormatOptions = {
  month: 'long',
  year: 'numeric',
};

/**
 * The locale every date in the app is formatted in.
 *
 * This used to be the constant `'en-US'`, and twelve sites hardcoded their own
 * `'en-US'` or `'en-GB'` besides — so a Dutch member reading a fully translated
 * screen still saw "Sep 16" where the rest of the app says "16 sep", and the two
 * charts disagreed with everything around them (class sweep H, 2026-09-17).
 *
 * It follows the **UI language**, not `settings.numberLocale`.
 * `docs/ARCHITECTURE.md` is explicit that those are different sets — the number
 * locale is CHECK-constrained to six values and describes grouping and decimal
 * separators, while the UI language is what the member is actually reading. A
 * French reader gets French month names without `fr-FR` having to be a legal
 * number locale.
 *
 * Set at one chokepoint by SettingsProvider, the same way
 * `setActiveNumberLocale` works — not threaded through call sites, so there is
 * no sweep to go stale. `null` until the provider mounts; nothing formats a date
 * at module-init time.
 */
let _activeDateLocale: string | null = null;

/** Called by SettingsProvider whenever the resolved UI language changes. */
export function setActiveDateLocale(locale: string | null): void {
  _activeDateLocale = locale;
}

/** The locale to pass to `toLocaleDateString` / `toLocaleTimeString`. */
export function dateLocale(): string {
  return _activeDateLocale ?? 'en-US';
}
