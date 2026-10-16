"""Trade notifications in the recipient's number style (2026-10-16).

Walked: "The seller countered with EUR19.00" to a Dutch member whose app shows
"EUR19". The trade's currency is kept; only the separators follow the reader.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.lib.money import trade_money  # noqa: E402


class Conn:
    def __init__(self, locale):
        self.locale = locale

    async def fetchval(self, sql, *args):
        return self.locale


def run(c, amount, cur="EUR"):
    return asyncio.run(trade_money(c, "u", amount, cur))


def test_dutch_reader_whole_amount_has_no_zero_cents():
    assert run(Conn("nl-NL"), 19.0) == "€19"


def test_cents_are_kept_and_use_the_readers_mark():
    assert run(Conn("nl-NL"), 17.5) == "€17,50"
    assert run(Conn("en-US"), 17.5) == "€17.50"


def test_trade_currency_is_kept_not_converted():
    assert run(Conn("nl-NL"), 20.0, "USD").startswith("$")


def test_no_settings_row_falls_back_cleanly():
    assert run(Conn(None), 22.5) == "€22.50"
