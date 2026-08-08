/**
 * Pins parseMoney against the four shapes that shipped as bugs.
 *
 * Every one of these produces a plausible NUMBER rather than an error, which is
 * why nothing caught them: no throw, no NaN, no empty list. The watchlist-builder
 * version turned a European "12,50" into 1250 and the row simply never fired.
 */
import { parseMoney } from '../../src/lib/format';

describe('parseMoney', () => {
  it('reads a comma decimal separator the way a European types it', () => {
    // The shipped bug: replace(/[^\d.]/g,'') made this 1250.
    expect(parseMoney('12,50')).toBe(12.5);
    expect(parseMoney('0,99')).toBe(0.99);
  });

  it('reads a dot decimal separator', () => {
    expect(parseMoney('12.50')).toBe(12.5);
  });

  it('strips currency symbols and spaces', () => {
    expect(parseMoney('€ 12,50')).toBe(12.5);
    expect(parseMoney('$1250')).toBe(1250);
    expect(parseMoney(' 12.50 ')).toBe(12.5);
  });

  it('treats the LAST separator as the decimal point', () => {
    // Thousands grouping, both conventions. Guessing from device locale would
    // be a coin flip on a number that decides what someone pays.
    expect(parseMoney('1.234,56')).toBe(1234.56);
    expect(parseMoney('1,234.56')).toBe(1234.56);
    expect(parseMoney('1 234,56')).toBe(1234.56);
  });

  it('returns null rather than a wrong number for unusable input', () => {
    // null, not NaN and not 0: 0 is a VALID price and would silently list
    // something as free.
    expect(parseMoney('')).toBeNull();
    expect(parseMoney('abc')).toBeNull();
    expect(parseMoney(null)).toBeNull();
    expect(parseMoney(undefined)).toBeNull();
    expect(parseMoney(12.5 as unknown as string)).toBeNull();
  });

  it('never returns a value 100x off, for any separator combination', () => {
    // The regression guard that matters: the original bug was a factor of 100.
    for (const input of ['12,50', '12.50', '€12,50', '12,5', '12.5']) {
      const n = parseMoney(input)!;
      expect(n).toBeGreaterThan(1);
      expect(n).toBeLessThan(100);
    }
  });
});
