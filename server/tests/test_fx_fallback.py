"""A stale FX fallback must not be pinned for the full cache window.

Found while checking US-market readiness, 2026-08-31. `get_rates` cached the
hardcoded fallback with the SAME ttl as live rates -- prod sets FX_CACHE_TTL to
28800 (8 hours, not the "1 hour" the module docstring claimed) -- so one
transient failure to reach Frankfurter froze a 7.1%-wrong USD rate for eight
hours across every ingest conversion and every client display, surfaced as a
single log warning.
"""
import pytest

import app.lib.fx_service as fx


class TestFallbackIsShortLived:
    @pytest.mark.asyncio
    async def test_a_FALLBACK_is_cached_briefly_not_for_the_full_ttl(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(fx, "cache_get", lambda k: None)
        monkeypatch.setattr(fx, "cache_set", lambda k, v, ttl: seen.update(ttl=ttl, rates=v))

        async def _dead():
            return None
        monkeypatch.setattr(fx, "_fetch_live_rates", _dead)

        await fx.get_rates()
        assert seen["ttl"] == fx._FALLBACK_TTL
        assert seen["ttl"] < fx._CACHE_TTL, (
            "a fallback cached for the live TTL turns a one-second outage into "
            "hours of known-wrong conversions"
        )

    @pytest.mark.asyncio
    async def test_LIVE_rates_still_get_the_full_ttl(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(fx, "cache_get", lambda k: None)
        monkeypatch.setattr(fx, "cache_set", lambda k, v, ttl: seen.update(ttl=ttl))

        async def _live():
            return {"USD": 0.8589, "EUR": 1.0}
        monkeypatch.setattr(fx, "_fetch_live_rates", _live)

        await fx.get_rates()
        assert seen["ttl"] == fx._CACHE_TTL

    @pytest.mark.asyncio
    async def test_the_outage_is_logged_at_ERROR_not_warning(self, monkeypatch, caplog):
        # A warning is something people scroll past. This is money converted at
        # a known-wrong rate.
        monkeypatch.setattr(fx, "cache_get", lambda k: None)
        monkeypatch.setattr(fx, "cache_set", lambda k, v, ttl: None)

        async def _dead():
            return None
        monkeypatch.setattr(fx, "_fetch_live_rates", _dead)

        with caplog.at_level("ERROR"):
            await fx.get_rates()
        assert any("LIVE RATES UNAVAILABLE" in r.message for r in caplog.records)


class TestRatesAreLive:
    def test_the_fallback_dict_is_recognised_as_NOT_live(self):
        assert fx.rates_are_live(dict(fx._FALLBACK_TO_EUR)) is False

    def test_real_ecb_rates_are_recognised_as_live(self):
        assert fx.rates_are_live({"USD": 0.858885, "GBP": 1.166589, "EUR": 1.0}) is True

    def test_an_empty_dict_is_not_live(self):
        # Absence is not evidence of freshness.
        assert fx.rates_are_live({}) is False


class TestTheFallbackItself:
    def test_the_hardcoded_USD_rate_is_documented_as_drifting(self):
        # Not asserting a VALUE -- it will drift and a test that pins it would
        # fail for the wrong reason. Asserting that the mechanism which limits
        # the damage is in place.
        assert fx._FALLBACK_TTL <= 900, "a fallback must expire in minutes, not hours"
        assert "EUR" in fx._FALLBACK_TO_EUR and fx._FALLBACK_TO_EUR["EUR"] == 1.0
