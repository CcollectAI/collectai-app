"""
The server and the client must not disagree about what a euro looks like.

WHY (2026-09-12, walking Notifications on Android): the list read
"EUR 42.75 for ..." while every price the app renders itself reads "€42,75".
`server/app/lib/money.py` now formats notification money, and its symbol table
is a SECOND copy of `CURRENCY_SYMBOLS` in `src/lib/format.ts`.

Two lists defining one thing is the shape that made `jewellery` browsable and
unfillable (learning_two_lists_define_the_same_thing). This test reads the
TypeScript source and compares the sets BOTH ways, because a parity check that
only walks one side is blind to a key the other side omits
(learning_a_parity_gate_is_blind_to_a_key_one_side_omits): if the client adds
CHF, the server would silently print "CHF 42.75" forever with nobody told.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.lib.money import CURRENCY_SYMBOLS, format_money

REPO = Path(__file__).resolve().parents[2]
FORMAT_TS = REPO / "src" / "lib" / "format.ts"


def _client_symbols() -> dict[str, str]:
    src = FORMAT_TS.read_text(encoding="utf-8")
    m = re.search(
        r"const CURRENCY_SYMBOLS:\s*Record<Currency, string>\s*=\s*\{(.*?)\}",
        src, re.S,
    )
    assert m, f"could not find CURRENCY_SYMBOLS in {FORMAT_TS} — did it move?"
    body = m.group(1)
    pairs = dict(re.findall(r"(\w+):\s*'([^']*)'", body))
    # A parse that silently finds nothing would make this whole file pass
    # vacuously, which is the failure mode it exists to prevent.
    assert len(pairs) >= 5, f"parsed only {len(pairs)} symbols from format.ts"
    return pairs


def test_server_and_client_cover_the_same_currencies():
    client = _client_symbols()
    assert set(CURRENCY_SYMBOLS) == set(client), (
        "currency lists drifted — "
        f"server-only={set(CURRENCY_SYMBOLS) - set(client)}, "
        f"client-only={set(client) - set(CURRENCY_SYMBOLS)}"
    )


def test_every_symbol_is_identical():
    client = _client_symbols()
    mismatched = {k: (CURRENCY_SYMBOLS[k], client[k])
                  for k in CURRENCY_SYMBOLS.keys() & client.keys()
                  if CURRENCY_SYMBOLS[k] != client[k]}
    assert not mismatched, f"symbol mismatch (server, client): {mismatched}"


@pytest.mark.parametrize("amount,currency,expected", [
    (42.75, "EUR", "€42.75"),
    (49.5, "USD", "$49.50"),
    (150, "GBP", "£150.00"),
    # No minor unit: "¥1200.00" is not a price written down in Japan.
    (1200, "JPY", "¥1200"),
    (99, "KRW", "₩99"),
    # Unknown code keeps the CODE and the space. Never guess a symbol: the
    # wrong mark on a real amount is worse than no mark.
    (42.75, "CHF", "CHF 42.75"),
    (42.75, None, "€42.75"),
])
def test_format_money(amount, currency, expected):
    assert format_money(amount, currency) == expected


def test_missing_amount_is_empty_not_zero():
    # 'withdrew from the  trade' reads as the bug it is. 'withdrew from the
    # €0.00 trade' tells a member their trade was for nothing.
    assert format_money(None, "EUR") == ""


# ---------------------------------------------------------------------------
# member_money (2026-09-26): notification money in the member's own currency and
# number format. Target Hit bodies read "€13.15" to a USD member and a dot to a
# Dutch one, while the app showed them "$15" / "€13,15".
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402
from unittest.mock import patch  # noqa: E402

from app.lib.money import member_money, format_money  # noqa: E402


class _Conn:
    def __init__(self, row):
        self.row = row

    async def fetchrow(self, sql, *args):
        return self.row


def _run(row, amount, rates=None):
    async def fake_rates():
        return rates or {"EUR": 1.0, "USD": 1.1}
    with patch("app.lib.fx_service.get_rates_from_eur", fake_rates):
        return asyncio.run(member_money(_Conn(row), "u1", amount))


def test_converts_to_the_members_currency():
    assert _run({"currency": "USD", "locale": "en-US"}, 10.0) == "$11.00"


def test_uses_the_members_separators():
    assert _run({"currency": "EUR", "locale": "nl-NL"}, 1253.5) == "€1.253,50"


def test_no_settings_row_is_plain_eur():
    assert _run(None, 13.15) == "€13.15"


def test_unknown_rate_stays_in_eur_rather_than_guessing():
    assert _run({"currency": "USD", "locale": "de-DE"}, 13.15, rates={"EUR": 1.0}) == "€13,15"


def test_sign_leads_the_symbol():
    assert format_money(-42.75, "EUR", "de-DE") == "-€42,75"
