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


# Separators per NumberLocale (src/lib/settings.tsx: the six the app offers).
# Comma-decimal locales write "€1.253,50"; the rest "€1,253.50". Unknown -> en.
_COMMA_DECIMAL = {"de-DE", "nl-NL"}


def _group(text: str, locale: str | None) -> str:
    """'1253.50' -> '1,253.50' or '1.253,50' for the member's number locale."""
    whole, _, frac = text.partition(".")
    neg = whole.startswith("-")
    digits = whole.lstrip("-")
    comma_dec = (locale or "") in _COMMA_DECIMAL
    sep = "." if comma_dec else ","
    grouped = ""
    while len(digits) > 3:
        grouped = sep + digits[-3:] + grouped
        digits = digits[:-3]
    grouped = ("-" if neg else "") + digits + grouped
    if not frac:
        return grouped
    return grouped + ("," if comma_dec else ".") + frac


def format_money(amount: float | int | None, currency: str | None = "EUR", locale: str | None = None) -> str:
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
    # Grouping and the decimal mark follow the member's NUMBER locale when the
    # caller knows it (member_money does). Without one, the old "42.75" shape.
    if locale:
        text = _group(text, locale)
    # A symbol abuts the number ("€42.75"); a bare CODE needs the space
    # ("CHF 42.75"), or it reads as one token.
    # The sign leads, as in src/lib/format.ts money(): "-€42,75", not "€-42,75".
    neg = text.startswith("-")
    text = text.lstrip("-")
    body = f"{sym}{text}" if sym != code else f"{sym} {text}"
    return f"-{body}" if neg else body


# ─── Platform fee ──────────────────────────────────────────────────────────
#
# ONE rate, because it was written SIX times (class sweep D, 2026-09-17):
# `int(ticket_price * 0.05)` in events_core.ticket-checkout, the same literal
# again in billing_router's webhook (which records what was charged), the
# organiser's hint in EventTicketingSection, and twice in app/legal/terms.tsx.
# They all said 5% — and the next person to change the rate had six places to
# find, two of which are legal copy a member can hold us to.
#
# The mirror of this constant is PLATFORM_FEE_PCT in src/constants/fees.ts, and
# `server/tests/test_platform_fee_parity.py` reads that file and fails if the two
# ever disagree — the same arrangement as CURRENCY_SYMBOLS above.
PLATFORM_FEE_PCT = 5


def platform_fee_cents(amount_cents: float | int | None) -> int:
    """The platform's cut of a paid ticket, in cents.

    Truncates, as both call sites did: the fee never rounds UP against the
    organiser. A missing or zero amount has no fee.
    """
    if not amount_cents:
        return 0
    return int(amount_cents * PLATFORM_FEE_PCT / 100)


async def member_money(conn, user_id: str, amount_eur: float | int | None) -> str:
    """A EUR amount as THIS member reads money: their currency, their separators.

    2026-09-26: Target Hit and Deal Agent notification bodies printed
    "€13.15" to everyone — euros to a USD member, a dot to a Dutch one — while
    the app shows that member "$15" / "€13,15". The server-side twin of the
    client's class AO fix. Any failure (no settings row, FX down) falls back
    to the plain EUR form rather than dropping the notification.
    """
    if amount_eur is None:
        return ""
    currency, locale = "EUR", None
    try:
        row = await conn.fetchrow(
            "SELECT currency, locale FROM public.user_settings WHERE user_id = $1::uuid",
            user_id,
        )
        if row:
            currency = (row["currency"] or "EUR").upper()
            locale = row["locale"]
        if currency != "EUR":
            from app.lib.fx_service import get_rates_from_eur
            rate = (await get_rates_from_eur()).get(currency)
            if not rate:
                return format_money(amount_eur, "EUR", locale)
            return format_money(float(amount_eur) * rate, currency, locale)
    except Exception:
        return format_money(amount_eur, "EUR")
    return format_money(amount_eur, currency, locale)

