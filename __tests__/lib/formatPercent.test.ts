/**
 * Percentages follow the member's number locale, like money does.
 *
 * 2026-09-23, walked on Android with a comma-decimal locale: "€60,00" beside
 * "+18.9%" on the same Analytics screen. Percentages were `.toFixed(1)}%`,
 * which always prints a dot.
 */
import { formatPercent, setActiveNumberLocale } from '@/lib/format';

afterEach(() => setActiveNumberLocale(null));

describe('formatPercent', () => {
  it('uses the comma decimal for a comma locale (the walked case)', () => {
    setActiveNumberLocale('nl-NL');
    expect(formatPercent(18.9, { sign: true })).toBe('+18,9%');
    expect(formatPercent(66.78, { decimals: 2 })).toBe('66,78%');
  });

  it('uses the dot decimal for en-US', () => {
    setActiveNumberLocale('en-US');
    expect(formatPercent(18.9, { sign: true })).toBe('+18.9%');
  });

  it('puts an ASCII hyphen before a loss, never inside', () => {
    setActiveNumberLocale('nl-NL');
    expect(formatPercent(-2.05, { decimals: 2 })).toBe('-2,05%');
  });

  it('gives no sign to a value that rounds to zero', () => {
    expect(formatPercent(0.04, { sign: true })).toBe('0.0%');
    expect(formatPercent(-0.04, { sign: true })).toBe('0.0%');
  });

  it('renders an unknown as a dash, never 0%', () => {
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent(Number.NaN)).toBe('—');
  });
});
