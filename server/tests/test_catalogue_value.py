"""One value per catalogue item (#12, 2026-09-27) — app/lib/catalogue_value.py."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.lib.catalogue_value import catalogue_value  # noqa: E402


class _Conn:
    def __init__(self, model=None, daily=None):
        self.model, self.daily = model, daily

    async def fetchrow(self, sql, *args):
        return self.model if "price_prediction_daily" in sql else self.daily


def _daily(n=10, median=100.0, latest=90.0, low=95.0, high=105.0):
    return {"comps_count": n, "p10": median, "median_price": median, "p90": median,
            "latest_price": latest, "low": low, "high": high}


def cv(model=None, daily=None):
    return asyncio.run(catalogue_value(_Conn(model, daily), "pokemon:k"))


def test_the_model_value_wins_over_the_median():
    r = cv({"q50": 825.41}, _daily(median=1159.04))
    assert (r["value"], r["source"]) == (825.41, "catalog_model")


def test_median_then_latest_when_the_model_has_no_value():
    assert cv(None, _daily(n=5, median=50.0))["source"] == "market_median"
    r = cv(None, _daily(n=2, median=50.0, latest=45.0))
    assert (r["value"], r["source"]) == (45.0, "latest_comp")


def test_nothing_priced_is_none():
    assert cv(None, _daily(n=0, median=None, latest=None, low=None, high=None)) is None


def test_disagreement_is_more_than_one_and_a_half_times():
    assert cv({"q50": 100.0}, _daily(low=100.0, high=150.0))["sources_disagree"] is False
    assert cv({"q50": 100.0}, _daily(low=100.0, high=151.0))["sources_disagree"] is True
    # A bulk card 9x apart but EUR 3.73 apart is noise, not a disagreement.
    assert cv({"q50": 0.56}, _daily(low=0.47, high=4.2))["sources_disagree"] is False
    # Base Set Charizard, measured on prod: TCGplayer 825 vs Cardmarket 1,531.
    assert cv({"q50": 825.41}, _daily(low=825.41, high=1531.0))["sources_disagree"] is True


def test_the_flag_survives_the_scan_response_mapping():
    """A field the response model does not declare is silently dropped (class V)."""
    from app.agents.intake_router import PriceBandResponse
    band = PriceBandResponse(q10=825.41, q50=825.41, q90=1531.0, confidence=0.9, sources_disagree=True)
    assert band.model_dump()["sources_disagree"] is True
