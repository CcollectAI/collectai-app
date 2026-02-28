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

/** Default locale for consistent formatting */
export const DATE_LOCALE = 'en-US';
