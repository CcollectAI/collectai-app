from __future__ import annotations

# NOTE: Replace with real FX service; this is a static fallback (EUR base).
FX_RATES = {
    "EUR": 1.0,
    "USD": 0.93,
    "GBP": 1.16,
    "JPY": 0.0062,
}


def to_eur(amount: float | None, currency: str | None) -> float | None:
    if amount is None or currency is None:
        return amount
    rate = FX_RATES.get(currency.upper())
    if rate is None:
        return amount  # fallback: unknown currency, keep as-is
    return round(float(amount) * rate, 2)
