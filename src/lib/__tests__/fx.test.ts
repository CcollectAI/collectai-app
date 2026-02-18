/**
 * Tests for src/lib/fx.ts — convertEUR, convertCurrency.
 *
 * Pure functions, no mocks needed.
 */

import { convertEUR, convertCurrency } from '../fx';
import type { Settings } from '../settings';

const FX_RATES: Settings['fxRates'] = { USD: 1.08, GBP: 0.86, JPY: 164.0 };

// ---------------------------------------------------------------------------
// convertEUR
// ---------------------------------------------------------------------------

describe('convertEUR', () => {
  it('EUR → EUR is passthrough', () => {
    const result = convertEUR(100, { currency: 'EUR', fxRates: FX_RATES });
    expect(result).toBe(100);
  });

  it('EUR → USD multiplies by USD rate', () => {
    const result = convertEUR(100, { currency: 'USD', fxRates: FX_RATES });
    expect(result).toBe(108);
  });

  it('EUR → GBP multiplies by GBP rate', () => {
    const result = convertEUR(100, { currency: 'GBP', fxRates: FX_RATES });
    expect(result).toBe(86);
  });

  it('missing rate falls back to * 1', () => {
    // fxRates doesn't contain JPY in this setup — wait, it does. Let's
    // use an incomplete fxRates object to test fallback.
    const result = convertEUR(100, {
      currency: 'JPY',
      fxRates: { USD: 1.08, GBP: 0.86 } as Settings['fxRates'],
    });
    // Missing JPY → rate defaults to 1
    expect(result).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// convertCurrency
// ---------------------------------------------------------------------------

describe('convertCurrency', () => {
  it('USD → EUR divides by USD rate', () => {
    // 100 USD / 1.08 ≈ 92.59
    const result = convertCurrency(100, 'USD', 'EUR', FX_RATES);
    expect(result).toBeCloseTo(100 / 1.08, 5);
  });

  it('EUR → USD multiplies by USD rate', () => {
    const result = convertCurrency(100, 'EUR', 'USD', FX_RATES);
    expect(result).toBe(108);
  });

  it('same currency is identity', () => {
    expect(convertCurrency(100, 'EUR', 'EUR', FX_RATES)).toBe(100);
    expect(convertCurrency(100, 'USD', 'USD', FX_RATES)).toBe(100);
  });

  it('GBP → USD via EUR pivot', () => {
    // GBP→EUR: 100 / 0.86 ≈ 116.28  →  EUR→USD: 116.28 * 1.08 ≈ 125.58
    const result = convertCurrency(100, 'GBP', 'USD', FX_RATES);
    expect(result).toBeCloseTo((100 / 0.86) * 1.08, 5);
  });
});
