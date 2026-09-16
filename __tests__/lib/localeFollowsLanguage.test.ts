/**
 * A date or a count that a member reads must follow what they are reading.
 *
 * Both halves shipped wrong and neither is visible to anyone testing in
 * English (class sweep H, 2026-09-17):
 *   - twelve sites formatted dates with a hard-coded 'en-US' / 'en-GB', so a
 *     Dutch member read "Sep 16" on an otherwise translated screen;
 *   - `formatNumber` defaulted to the literal 'de-DE', and 8 of its 14 call
 *     sites pass no locale, so counts were grouped German for everybody.
 */
import { dateLocale, setActiveDateLocale } from '../../src/constants/dateFormats';
import { formatNumber, setActiveNumberLocale } from '../../src/lib/format';

afterEach(() => {
  setActiveDateLocale(null);
  setActiveNumberLocale(null);
});

describe('dateLocale', () => {
  it('falls back to en-US before the provider mounts', () => {
    setActiveDateLocale(null);
    expect(dateLocale()).toBe('en-US');
  });

  it('follows the resolved UI language', () => {
    setActiveDateLocale('nl');
    expect(dateLocale()).toBe('nl');
  });

  it('actually changes how a date renders', () => {
    const d = new Date('2026-09-16T12:00:00Z');
    setActiveDateLocale('en-US');
    const us = d.toLocaleDateString(dateLocale(), { month: 'short', day: 'numeric' });
    setActiveDateLocale('nl');
    const nl = d.toLocaleDateString(dateLocale(), { month: 'short', day: 'numeric' });
    expect(us).not.toBe(nl);
  });
});

describe('formatNumber', () => {
  it('follows the active number locale when no locale is passed', () => {
    setActiveNumberLocale('de-DE');
    const de = formatNumber(1234567);
    setActiveNumberLocale('en-US');
    const us = formatNumber(1234567);
    expect(de).not.toBe(us);
    expect(us).toBe('1,234,567');
  });

  it('does not silently render German grouping when nothing is set', () => {
    // The old default was the literal 'de-DE'.
    setActiveNumberLocale(null);
    expect(formatNumber(1234)).toBe('1,234');
  });

  it('still honours an explicit locale argument', () => {
    setActiveNumberLocale('en-US');
    expect(formatNumber(1234, 'de-DE')).toBe('1.234');
  });
});
