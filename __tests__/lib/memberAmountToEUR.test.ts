import { memberAmountToEUR } from '../../src/lib/fx';
import { fmtCurrency } from '../../src/lib/format';

// 1 EUR = 1.10 USD, 1 EUR = 160 JPY
const usd = { currency: 'USD' as const, fxRates: { USD: 1.1, JPY: 160 } as Record<string, number> };
const jpy = { currency: 'JPY' as const, fxRates: { USD: 1.1, JPY: 160 } as Record<string, number> };
const eur = { currency: 'EUR' as const, fxRates: {} as Record<string, number> };

describe('memberAmountToEUR — what a member types is stored in EUR', () => {
  it('converts a USD member typed amount', () => {
    expect(memberAmountToEUR(110, usd)).toBeCloseTo(100, 2);
  });

  it('converts a JPY member typed amount (the 160x case)', () => {
    expect(memberAmountToEUR(16000, jpy)).toBeCloseTo(100, 2);
  });

  it('leaves a EUR member amount alone', () => {
    expect(memberAmountToEUR(100, eur)).toBe(100);
  });

  it('round-trips: typed -> stored EUR -> displayed is what they typed', () => {
    const typed = 250;
    const storedEur = memberAmountToEUR(typed, usd);
    const shown = fmtCurrency(storedEur, { ...usd, numberLocale: 'en-US' as const });
    expect(shown).toContain('250');
  });
});
