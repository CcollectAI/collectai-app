/**
 * Tests for src/lib/format.ts — fmtCurrency, formatPrice, formatNumber.
 *
 * All functions under test are pure (Intl.NumberFormat based), so no mocks
 * are needed.
 */

import { fmtCurrency, formatPrice, formatNumber } from '../format';
import type { Settings } from '../settings';

// Minimal settings helper
function makeSettings(
  overrides: Partial<Pick<Settings, 'currency' | 'numberLocale' | 'fxRates'>> = {},
): Pick<Settings, 'currency' | 'numberLocale' | 'fxRates'> {
  return {
    currency: 'EUR',
    numberLocale: 'de-DE',
    fxRates: { USD: 1.08, GBP: 0.86, JPY: 164.0 },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// fmtCurrency
// ---------------------------------------------------------------------------

describe('fmtCurrency', () => {
  it('formats EUR → EUR', () => {
    const s = makeSettings({ currency: 'EUR', numberLocale: 'de-DE' });
    const result = fmtCurrency(100, s);
    // German locale uses non-breaking space: "100 €" or "100\u00a0€"
    expect(result).toContain('100');
    expect(result).toContain('€');
  });

  it('converts EUR → USD using fxRates', () => {
    const s = makeSettings({ currency: 'USD', numberLocale: 'en-US' });
    const result = fmtCurrency(100, s);
    // 100 EUR * 1.08 = 108 USD → "$108"
    expect(result).toContain('$');
    expect(result).toContain('108');
  });

  it('formats zero', () => {
    const s = makeSettings({ currency: 'EUR', numberLocale: 'de-DE' });
    const result = fmtCurrency(0, s);
    expect(result).toContain('0');
    expect(result).toContain('€');
  });
});

// ---------------------------------------------------------------------------
// formatPrice
// ---------------------------------------------------------------------------

describe('formatPrice', () => {
  it('formats EUR amount', () => {
    const result = formatPrice(1234, 'EUR');
    expect(result).toContain('€');
    expect(result).toContain('1');
  });

  it('formats USD amount', () => {
    const result = formatPrice(1234, 'USD');
    expect(result).toContain('$');
    expect(result).toContain('1');
  });

  it('formats JPY amount', () => {
    const result = formatPrice(1234, 'JPY');
    expect(result).toContain('￥');
  });

  it('formats GBP amount', () => {
    const result = formatPrice(1234, 'GBP');
    expect(result).toContain('£');
  });

  it('returns dash for null', () => {
    expect(formatPrice(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatPrice(undefined)).toBe('—');
  });

  it('returns dash for NaN', () => {
    expect(formatPrice(NaN)).toBe('—');
  });
});

// ---------------------------------------------------------------------------
// formatNumber
// ---------------------------------------------------------------------------

describe('formatNumber', () => {
  it('formats with de-DE locale', () => {
    const result = formatNumber(1234, 'de-DE');
    // German uses dot as thousand separator
    expect(result).toBe('1.234');
  });

  it('returns dash for null', () => {
    expect(formatNumber(null)).toBe('—');
  });
});
