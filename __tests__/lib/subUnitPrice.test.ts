/**
 * A 30-cent card is not worthless.
 *
 * 2026-09-17, found by reading a catalogue screenshot ("~€1" for a median of 213
 * prices) and then the formatter: `money()` used maximumFractionDigits: 0 for
 * every amount, so anything under €1 printed as `€0` — and `€0` is the string
 * this app uses for "we do not know what this is worth" (`isUnpriced`). On
 * production **885,445** catalogue prices sit between 0 and 1, i.e. the majority
 * of the cheap catalogue was displayed as worthless.
 *
 * 0 decimals stays the rule everywhere else: it is deliberate, and a portfolio
 * total of €1.348 must not grow cents.
 */
import { formatPrice, setActiveNumberLocale } from '../../src/lib/format';

describe('sub-unit prices', () => {
  beforeEach(() => setActiveNumberLocale('en-US'));

  it('shows cents below one unit instead of rounding to zero', () => {
    expect(formatPrice(0.3, 'EUR')).toBe('€0.30');
    expect(formatPrice(0.05, 'EUR')).toBe('€0.05');
    expect(formatPrice(0.99, 'EUR')).toBe('€0.99');
  });

  it('says "under a cent" rather than printing €0.00', () => {
    expect(formatPrice(0.004, 'EUR')).toBe('<€0.01');
    expect(formatPrice(0.0001, 'USD')).toBe('<$0.01');
  });

  it('keeps 0 decimals at and above one unit', () => {
    expect(formatPrice(1, 'EUR')).toBe('€1');
    expect(formatPrice(1.35, 'EUR')).toBe('€1');
    expect(formatPrice(1348, 'EUR')).toBe('€1,348');
  });

  it('reports sub-unit amounts as "under one" for currencies with no minor unit', () => {
    expect(formatPrice(0.4, 'JPY')).toBe('<¥1');
    expect(formatPrice(0.4, 'KRW')).toBe('<₩1');
    expect(formatPrice(48, 'JPY')).toBe('¥48');
  });

  it('a true zero is still zero — the unpriced rule lives above this layer', () => {
    expect(formatPrice(0, 'EUR')).toBe('€0');
  });

  it('follows the number locale for the decimal separator', () => {
    setActiveNumberLocale('de-DE');
    expect(formatPrice(0.3, 'EUR')).toBe('€0,30');
    expect(formatPrice(1348, 'EUR')).toBe('€1.348');
  });

  it('puts the sign OUTSIDE the symbol — `-€10`, never `€-10`', () => {
    // `€-10` is a shape the screen sweep flags as raw output, and every screen
    // that renders a loss writes `-{formatPrice(...)}` itself, so this was the
    // one spelling nothing in the app agreed with.
    setActiveNumberLocale('en-US');
    expect(formatPrice(-0.3, 'EUR')).toBe('-€0.30');
    expect(formatPrice(-10, 'EUR')).toBe('-€10');
    expect(formatPrice(-1348, 'EUR')).toBe('-€1,348');
  });
});
