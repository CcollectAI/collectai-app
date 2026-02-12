import type { Currency, Settings } from './settings';

/** Convert an amount in EUR to the target currency using the rates in Settings. */
export function convertEUR(amountEUR: number, s: Pick<Settings,'currency'|'fxRates'>): number {
  if (s.currency === 'EUR') return amountEUR;
  const rate = (s.fxRates as Record<string,number>)?.[s.currency] ?? 1;
  return amountEUR * rate;
}

/** Convert between any two supported currencies via EUR as pivot. */
export function convertCurrency(
  amount: number,
  from: Currency,
  to: Currency,
  fxRates: Settings['fxRates'],
): number {
  if (from === to) return amount;
  // Convert to EUR first
  const ratesFromEUR = { EUR: 1, ...fxRates } as Record<string,number>;
  const amountEUR = from === 'EUR' ? amount : amount / (ratesFromEUR[from] || 1);
  // Then convert to target
  return to === 'EUR' ? amountEUR : amountEUR * (ratesFromEUR[to] || 1);
}
