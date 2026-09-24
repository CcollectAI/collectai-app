/**
 * Compact money and the money input placeholder follow the member's currency
 * and number locale.
 *
 * 2026-09-24: profile cards printed `€${v/1000}k` — euros for every member,
 * never converted — and money inputs showed a literal "0.00" to members whose
 * decimal is a comma.
 */
import { fmtCurrencyCompact, moneyInputPlaceholder, moneyInputValue, setActiveNumberLocale } from '@/lib/format';

afterEach(() => setActiveNumberLocale(null));

const eur = { currency: 'EUR' as const, numberLocale: 'nl-NL' as const, fxRates: {} };
const usd = { currency: 'USD' as const, numberLocale: 'en-US' as const, fxRates: { USD: 1.1 } };

describe('fmtCurrencyCompact', () => {
  it('converts before shortening (the defect: euros shown to a USD member)', () => {
    expect(fmtCurrencyCompact(2000, usd)).toBe('$2.2k');
  });
  it('uses the member decimal separator', () => {
    expect(fmtCurrencyCompact(1250, eur)).toBe('€1,3k');
  });
  it('is plain money below the threshold', () => {
    expect(fmtCurrencyCompact(900, usd)).toBe('$990');
    expect(fmtCurrencyCompact(50000, usd, 100000)).toMatch(/^\$55,000$/);
  });
});

describe('moneyInputPlaceholder', () => {
  it('shows the comma decimal to a comma locale', () => {
    setActiveNumberLocale('nl-NL');
    expect(moneyInputPlaceholder()).toBe('0,00');
  });
  it('shows the dot decimal to en-US', () => {
    setActiveNumberLocale('en-US');
    expect(moneyInputPlaceholder()).toBe('0.00');
  });
});

describe('moneyInputValue', () => {
  it('seeds a comma-decimal member with a comma, rounded to cents', () => {
    setActiveNumberLocale('nl-NL');
    expect(moneyInputValue(5.535)).toBe('5,54');
    expect(moneyInputValue(30)).toBe('30');
  });
  it('never groups thousands in an input (parseMoney would misread it)', () => {
    setActiveNumberLocale('en-US');
    expect(moneyInputValue(12000.5)).toBe('12000.5');
  });
  it('is empty for no amount', () => {
    expect(moneyInputValue(null)).toBe('');
  });
});
