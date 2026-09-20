import { fmtCurrency } from '@/lib/format';
const s = (currency: any, numberLocale: string) => ({ currency, numberLocale, fxRates: {} } as any);
describe('money cents opt-in', () => {
  it('default stays whole euros', () => expect(fmtCurrency(56.25, s('EUR','nl-NL'))).toBe('€56'));
  it('cents:true shows minor units', () => expect(fmtCurrency(56.25, s('EUR','nl-NL'), { cents: true })).toBe('€56,25'));
  it('negative keeps the sign outside the symbol', () => expect(fmtCurrency(-56.25, s('EUR','nl-NL'), { cents: true })).toBe('-€56,25'));
  it('JPY has no minor unit, so cents is ignored', () => expect(fmtCurrency(5625, s('JPY','ja-JP'), { cents: true })).not.toContain('.'));
  it('sub-unit rule still wins', () => expect(fmtCurrency(0.3, s('EUR','nl-NL'))).toBe('€0,30'));
});
