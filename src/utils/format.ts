// Re-export canonical formatters — prefer these over inline Intl.NumberFormat
export { fmtCurrency, formatPrice, formatNumber } from '../lib/format';

/** Legacy helper — prefer formatPrice() for currency-aware display */
export const fmtMoney = (n: number) =>
  new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);

export const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
