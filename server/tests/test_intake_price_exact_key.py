"""A matched catalogue key is priced EXACTLY (2026-09-26).

QuickScan matched Base Set Charizard (base1-base1-4, EUR 1,159 on its catalogue
page) and quoted EUR 2.97: the key went into `normalized_key ILIKE '%key%'`,
and 'base1-base1-4' is a substring of base1-base1-40..49 — commons.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.intake.enrichment import _estimate_price  # noqa: E402


class _Conn:
    def __init__(self, log, daily_row, hits):
        self.log, self.daily_row, self.hits = log, daily_row, hits

    async def fetchrow(self, sql, *args):
        self.log.append((sql, args))
        return self.daily_row if "market_hits_daily" in sql else None

    async def fetch(self, sql, *args):
        self.log.append((sql, args))
        return self.hits


class _Pool:
    def __init__(self, daily_row=None, hits=None):
        self.log = []
        self.daily_row, self.hits = daily_row, hits or []

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                return _Conn(pool.log, pool.daily_row, pool.hits)

            async def __aexit__(self_inner, *a):
                return False

        return _Ctx()


def test_matched_key_reads_the_daily_rollup_by_exact_item_ref():
    pool = _Pool(daily_row={"n": 108, "q10": 700.0, "q50": 1159.04, "q90": 1500.0})
    price, source, band = asyncio.run(
        _estimate_price("pokemon", "Charizard", pool, catalog_match_key="base1-base1-4")
    )
    assert (price, source) == (1159.04, "market_hits_daily")
    sql, args = pool.log[0]
    assert "market_hits_daily" in sql and args == ("pokemon:base1-base1-4",)


def test_raw_fallback_for_a_matched_key_is_equality_not_substring():
    pool = _Pool(daily_row={"n": 0, "q10": None, "q50": None, "q90": None})
    asyncio.run(_estimate_price("pokemon", "Charizard", pool, catalog_match_key="base1-base1-4"))
    raw = [(s, a) for s, a in pool.log if "FROM market_hits\n" in s or "FROM market_hits " in s]
    assert raw, "the raw market_hits fallback never ran"
    sql, args = raw[0]
    assert "normalized_key = $1" in sql and "ILIKE" not in sql.split("WHERE", 1)[1].split("AND", 1)[0]
    assert args[0] == "base1-base1-4"


def test_no_key_still_searches_by_name():
    pool = _Pool()
    asyncio.run(_estimate_price("pokemon", "Charizard", pool))
    assert not any("market_hits_daily" in s for s, _ in pool.log)
    sql, args = next((s, a) for s, a in pool.log if "normalized_key" in s)
    assert "ILIKE" in sql and args[0] == "%Charizard%"
