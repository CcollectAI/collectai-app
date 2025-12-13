import { Settings } from './settings';
import { convertEUR } from './fx';

/** Format a EUR amount into the selected currency using Settings.fxRates, then stringify for display. */
export function fmtCurrency(amountEUR:number, s:Pick<Settings,'currency'|'numberLocale'|'fxRates'>){
  const val = convertEUR(amountEUR, s as any);
  return new Intl.NumberFormat(s.numberLocale, { style:'currency', currency: s.currency, maximumFractionDigits: 0 }).format(val);
}
