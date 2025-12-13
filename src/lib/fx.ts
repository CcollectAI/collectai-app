import { Settings } from './settings';
export function convertEUR(amountEUR: number, s: Pick<Settings,'currency'|'fxRates'>): number {
  if (s.currency === 'EUR') return amountEUR;
  const rate = s.fxRates?.[s.currency] ?? 1;
  return amountEUR * rate;
}
