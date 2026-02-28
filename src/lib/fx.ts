import type { Currency, Settings } from './settings';

// ---------------------------------------------------------------------------
// Module-level FX rate cache
// ---------------------------------------------------------------------------
// Default rates per 1 EUR — kept in sync with settings.tsx DEFAULTS.
// SettingsProvider calls `updateFxCache()` whenever live rates arrive,
// so adapters that cannot use React hooks can still get current rates.
const DEFAULT_RATES: Settings['fxRates'] = {
  USD: 1.08, GBP: 0.86, JPY: 164.0, KRW: 1490, AUD: 1.67, CAD: 1.52,
};

let _cachedRates: Settings['fxRates'] = { ...DEFAULT_RATES };

/** Called by SettingsProvider when live FX rates are fetched. */
export function updateFxCache(rates: Settings['fxRates']): void {
  _cachedRates = { ...rates };
}

/** Get the current FX rates (live if available, otherwise defaults). */
export function getFxRates(): Settings['fxRates'] {
  return _cachedRates;
}

/**
 * Quick conversion from any currency to EUR using cached rates.
 * Useful for market adapters that receive prices in USD/GBP/etc.
 */
export function toEUR(amount: number, from: Currency): number {
  if (from === 'EUR') return amount;
  const rate = (_cachedRates as Record<string, number>)[from] ?? 1;
  return Math.round((amount / rate) * 100) / 100;
}

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
