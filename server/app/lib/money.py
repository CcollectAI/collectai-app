"""
One way to write an amount into text a member reads.

WHY (2026-09-12, found walking the Notifications screen on Android): three
notification bodies in `p2p_offers_router.py` composed money as
`f"{currency} {amount:.2f}"`, so the list read

    EUR 42.75 for "DEMO Charizard Base Set Holo".

while every price the app renders itself is `€42,75` — `src/lib/format.ts`
leads with the SYMBOL, and `notify.py`'s own usage docstring already shows the
house style ("Your Charizard dropped to €150"). The router was the outlier, and
nothing named the convention, so there was nothing to be an outlier FROM.

The symbol table mirrors `CURRENCY_SYMBOLS` in `src/lib/format.ts`. Two copies
of one list is the shape that let `jewellery` be browsable and unfillable
(learning_two_lists_define_the_same_thing), so
`server/tests/test_currency_symbol_parity.py` reads the TypeScript file and
fails if they ever disagree — including if the client gains a currency this
file has never heard of.

An unknown code falls back to the code itself ("CHF 42.75"), never to a wrong
symbol: showing the wrong currency's mark on a real amount is worse than
showing no mark at all.
"""
from __future__ import annotations

# Mirror of CURRENCY_SYMBOLS in src/lib/format.ts. Keep in sync — the parity
# test is what enforces it.
CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "JPY": "¥",
    "KRW": "₩",
    "AUD": "A$",
    "CAD": "C$",
}


def currency_symbol(code: str | None) -> str:
    """Symbol for a currency code, or the code itself when we do not know it."""
    if not code:
        return ""
    return CURRENCY_SYMBOLS.get(code.upper(), code.upper())


def format_money(amount: float | int | None, currency: str | None = "EUR") -> str:
    """
    Money for a notification body: "€42.75", "¥1200", "CHF 42.75".

    Zero-decimal currencies print no fraction — "¥1200.00" is not a price a
    Japanese member has ever seen written down. Everything else gets two
    places, because a trade amount is exact and rounding it in the text would
    disagree with the number the member sees in the offer screen.

    A missing amount returns "" rather than "0.00": the caller composing
    'withdrew from the  trade' reads as a bug, which it is, and is far better
    than telling someone a trade was for nothing.
    """
    if amount is None:
        return ""
    code = (currency or "EUR").upper()
    sym = currency_symbol(code)
    # JPY and KRW have no minor unit.
    text = f"{amount:.0f}" if code in ("JPY", "KRW") else f"{amount:.2f}"
    # A symbol abuts the number ("€42.75"); a bare CODE needs the space
    # ("CHF 42.75"), or it reads as one token.
    return f"{sym}{text}" if sym != code else f"{sym} {text}"
