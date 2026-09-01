"""A spent plan must stop the calls, not repeat them.

The watchdog reported bake erroring for 30 minutes; it had been erroring for two
days. `[Firecrawl] /search HTTP 402` first appeared 2026-08-30 and ran 79 times
on 2026-09-01 alone. Measured: remaining_credits -2 of 1000, billing period
ending 2026-09-04 — overdrawn, three days from resetting.

firecrawl_client special-cased 429 and nothing else, so a 402 fell through,
logged, returned None, and the next cycle tried again. A rate limit is transient
and worth retrying; a spent plan is not.
"""
import pytest

from app.lib import firecrawl_quota as q


@pytest.fixture(autouse=True)
def _cache(monkeypatch):
    store = {}
    monkeypatch.setattr(q, "cache_get", lambda k: store.get(k))
    monkeypatch.setattr(q, "cache_set", lambda k, v, ttl=None: store.__setitem__(k, (v)))
    return store


class TestNoteExhausted:
    def test_a_402_latches_suppression(self, _cache):
        q.note_exhausted()
        assert _cache[q._EXHAUSTED_KEY] is True

    def test_it_logs_at_ERROR_naming_the_cause(self, caplog):
        with caplog.at_level("ERROR"):
            q.note_exhausted()
        msg = " ".join(r.message for r in caplog.records)
        assert "PLAN SPENT" in msg and "not a rate limit" in msg

    def test_a_malformed_billing_date_does_not_mute_for_a_month(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(q, "cache_set", lambda k, v, ttl=None: seen.update(ttl=ttl))
        q.note_exhausted("not-a-date")
        assert seen["ttl"] == q._MAX_BACKOFF_S
        assert seen["ttl"] <= 6 * 3600, "a misread date must not silence scraping for weeks"

    def test_an_absurd_billing_date_is_rejected(self, monkeypatch):
        # A year away would mute Firecrawl until next summer.
        seen = {}
        monkeypatch.setattr(q, "cache_set", lambda k, v, ttl=None: seen.update(ttl=ttl))
        q.note_exhausted("2099-01-01T00:00:00Z")
        assert seen["ttl"] == q._MAX_BACKOFF_S


class TestAllow:
    @pytest.mark.asyncio
    async def test_blocks_once_exhausted(self, _cache):
        _cache[q._EXHAUSTED_KEY] = True
        assert await q.allow() is False

    @pytest.mark.asyncio
    async def test_blocks_at_the_reserve_not_at_zero(self, monkeypatch):
        async def _fetch():
            return {"remaining_credits": 5, "billing_period_end": None}
        monkeypatch.setattr(q, "fetch_credits", _fetch)
        assert await q.allow() is False

    @pytest.mark.asyncio
    async def test_allows_with_credits_to_spare(self, monkeypatch):
        async def _fetch():
            return {"remaining_credits": 900, "billing_period_end": None}
        monkeypatch.setattr(q, "fetch_credits", _fetch)
        assert await q.allow() is True

    @pytest.mark.asyncio
    async def test_the_REAL_measured_state_blocks(self, monkeypatch):
        # remaining_credits -2 — the state that produced 79 errors in a day.
        async def _fetch():
            return {"remaining_credits": -2, "billing_period_end": "2026-09-04T20:03:15.505Z"}
        monkeypatch.setattr(q, "fetch_credits", _fetch)
        assert await q.allow() is False

    @pytest.mark.asyncio
    async def test_an_unreachable_usage_endpoint_ALLOWS(self, monkeypatch):
        """Deliberately different from scrapedo_quota, which fails CLOSED.

        Scrape.do has a hard monthly cap that silently truncates; Firecrawl
        bills instead. Failing closed on one unreachable request would take
        scraping down for a transient, and a real 402 latches suppression
        anyway.
        """
        async def _fetch():
            return None
        monkeypatch.setattr(q, "fetch_credits", _fetch)
        assert await q.allow() is True


class TestTheClientHandles402:
    def test_both_call_paths_special_case_402(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "app" / "lib" / "firecrawl_client.py").read_text()
        assert src.count("resp.status_code == 402") == 2, (
            "both /scrape and /search must treat 402 as a spent plan; the one "
            "that does not will keep retrying forever"
        )
        assert src.count("firecrawl_quota.allow()") == 2
