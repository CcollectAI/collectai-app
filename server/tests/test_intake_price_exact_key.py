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
    def __init__(self, log, daily_row, hits, model_row=None):
        self.log, self.daily_row, self.hits, self.model_row = log, daily_row, hits, model_row

    async def fetchrow(self, sql, *args):
        self.log.append((sql, args))
        if "price_prediction_daily" in sql:
            return self.model_row
        return self.daily_row if "market_hits_daily" in sql else None

    async def fetch(self, sql, *args):
        self.log.append((sql, args))
        return self.hits


class _Pool:
    def __init__(self, daily_row=None, hits=None, model_row=None):
        self.log = []
        self.daily_row, self.hits, self.model_row = daily_row, hits or [], model_row

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                return _Conn(pool.log, pool.daily_row, pool.hits, pool.model_row)

            async def __aexit__(self_inner, *a):
                return False

        return _Ctx()


def _daily(n, median, low=None, high=None):
    return {"comps_count": n, "p10": median, "median_price": median, "p90": median,
            "latest_price": median, "low": low, "high": high}


def test_matched_key_is_priced_by_the_catalogue_model_by_exact_item_ref():
    """#12 (2026-09-27): the scan shows the number the saved item will show.
    Base Set Charizard: model 825 (TCGplayer), sources 825 / 1,531 — the old
    median-of-medians said 1,159, their midpoint."""
    pool = _Pool(daily_row=_daily(108, 1159.04, low=825.41, high=1531.0), model_row={"q50": 825.41})
    price, source, band = asyncio.run(
        _estimate_price("pokemon", "Charizard", pool, catalog_match_key="base1-base1-4")
    )
    assert (price, source) == (825.41, "catalog_model")
    assert all(args == ("pokemon:base1-base1-4",) for _, args in pool.log[:2])
    # 1,531 / 825 = 1.9x apart: the band is the source spread, flagged.
    assert band["sources_disagree"] is True
    assert (band["q10"], band["q90"]) == (825.41, 1531.0)


def test_agreeing_sources_are_not_flagged():
    pool = _Pool(daily_row=_daily(40, 100.0, low=95.0, high=110.0), model_row={"q50": 100.0})
    _, _, band = asyncio.run(_estimate_price("pokemon", "X", pool, catalog_match_key="k"))
    assert band["sources_disagree"] is False


def test_without_a_model_value_the_daily_median_prices_it():
    pool = _Pool(daily_row=_daily(12, 50.0, low=48.0, high=52.0), model_row=None)
    price, source, _ = asyncio.run(_estimate_price("pokemon", "X", pool, catalog_match_key="k"))
    assert (price, source) == (50.0, "market_median")


def test_raw_fallback_for_a_matched_key_is_equality_not_substring():
    pool = _Pool(daily_row=_daily(0, None))
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
