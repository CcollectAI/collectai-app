/**
 * The Sell flow's price field is `compose(required('Price'), positiveNumber('Price'))`.
 * `Number("12,50")` is NaN, so every member who types a comma decimal — most of
 * the seven currencies this app ships — was told "Price must be a number" and
 * could not list at all (2026-09-16, class sweep E).
 *
 * The second half of this file is the trap that came WITH the fix: parseMoney is
 * a reader, not a validator. It strips anything that is not a digit or a
 * separator, so "12abc" reads as 12 and "-5" as 5 — which would accept a
 * negative price as positive.
 */
import { numeric, positiveNumber } from '../../src/lib/validate';

const price = positiveNumber('Price');
const num = numeric('Amount');

describe('numeric / positiveNumber accept what a member actually types', () => {
  it('accepts a comma decimal separator', () => {
    expect(price('12,50')).toBeNull();
    expect(num('12,50')).toBeNull();
  });

  it('accepts a dot decimal and a thousands group', () => {
    expect(price('12.50')).toBeNull();
    expect(price('1.250,00')).toBeNull();
    expect(price('1,234.56')).toBeNull();
    expect(price('1 234,56')).toBeNull();
  });

  it('accepts a currency symbol the member pasted in', () => {
    expect(price('€ 45')).toBeNull();
  });

  it('lets `required` handle an empty field', () => {
    expect(price('')).toBeNull();
    expect(price('   ')).toBeNull();
  });
});

describe('…and still reject what is not a number', () => {
  it('rejects text, and text glued to a number', () => {
    expect(price('abc')).toBe('Price must be a number');
    // parseMoney('12abc') is 12 — the validator must not inherit that.
    expect(price('12abc')).toBe('Price must be a number');
    expect(price('1e3')).toBe('Price must be a number');
  });

  it('rejects a negative price AS negative, not as its absolute value', () => {
    // parseMoney('-5') is 5: the sign is stripped with the currency symbol.
    expect(price('-5')).toBe('Price must be greater than 0');
    expect(price('-12,50')).toBe('Price must be greater than 0');
  });

  it('rejects zero', () => {
    expect(price('0')).toBe('Price must be greater than 0');
    expect(price('0,00')).toBe('Price must be greater than 0');
  });
});
