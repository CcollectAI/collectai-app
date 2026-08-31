"""The 1,000/month free tier must be metered against Scrape.do's OWN count.

`spend_tracker` looks like it covers this and does not: it compares one shared
EUR pool across every provider, and scrapedo is EUR 0.001/call — the whole
1,000-request tier is EUR 1, so that budget can never block before the hard cap
is gone. It is also in-memory, so a bake restart zeroes it while the real quota
keeps counting.
"""
import pytest

from app.lib import scrapedo_quota as q


@pytest.fixture(autouse=True)
def _clear(monkeypatch):
    store = {}
    monkeypatch.setattr(q, "cache_get", lambda k: store.get(k))
    monkeypatch.setattr(q, "cache_set", lambda k, v, ttl=None: store.__setitem__(k, v))
    return store


class TestAllow:
    @pytest.mark.asyncio
    async def test_allows_when_well_under_the_cap(self, monkeypatch):
        async def _fetch(timeout=15.0):
            return 1000
        monkeypatch.setattr(q, "fetch_remaining", _fetch)
        assert await q.allow(reserve=100) is True

    @pytest.mark.asyncio
    async def test_BLOCKS_at_the_reserve_not_at_zero(self, monkeypatch):
        """Our view is up to _CACHE_TTL stale, so the reserve absorbs the calls
        made inside that window. Stopping at 0 means learning about the overrun
        from a 429."""
        async def _fetch(timeout=15.0):
            return 100
        monkeypatch.setattr(q, "fetch_remaining", _fetch)
        assert await q.allow(reserve=100) is False

    @pytest.mark.asyncio
    async def test_BLOCKS_when_the_quota_cannot_be_READ(self, monkeypatch, caplog):
        """Fails CLOSED. "We could not ask" must never read as "plenty left" —
        a missed comp costs one row, overrunning a hard cap costs the month."""
        async def _fetch(timeout=15.0):
            return None
        monkeypatch.setattr(q, "fetch_remaining", _fetch)
        with caplog.at_level("ERROR"):
            assert await q.allow() is False
        assert any("BLOCKING" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_falls_back_to_a_STALE_count_rather_than_going_dark(self, monkeypatch, _clear):
        # One flaky /info must not disable the adapter; an expired count is a
        # far better guide than no count.
        _clear[q._CACHE_KEY] = 800
        async def _fetch(timeout=15.0):
            return None
        monkeypatch.setattr(q, "fetch_remaining", _fetch)
        assert await q.remaining() == 800
        assert await q.allow(reserve=100) is True


class TestFetchRemaining:
    @pytest.mark.asyncio
    async def test_a_non_integer_remaining_is_None_not_zero(self, monkeypatch):
        """A shape change at Scrape.do must not read as "no quota left" OR as
        "plenty" — both are claims we cannot support."""
        class _Resp:
            def raise_for_status(self): pass
            def json(self): return {"RemainingMonthlyRequest": "lots"}
        class _Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, *a, **k): return _Resp()
        monkeypatch.setattr(q.httpx, "AsyncClient", lambda **k: _Client())
        monkeypatch.setattr(q, "SCRAPEDO_API_KEY", "x")
        assert await q.fetch_remaining() is None

    @pytest.mark.asyncio
    async def test_no_api_key_is_None(self, monkeypatch):
        monkeypatch.setattr(q, "SCRAPEDO_API_KEY", "")
        assert await q.fetch_remaining() is None


class TestNoteRequestMade:
    def test_decrements_the_cached_view(self, _clear):
        # Without this the cached count sits flat for the whole TTL and a burst
        # inside that window is invisible.
        _clear[q._CACHE_KEY] = 500
        q.note_request_made()
        assert _clear[q._CACHE_KEY] == 499

    def test_never_goes_negative_and_tolerates_an_empty_cache(self, _clear):
        _clear[q._CACHE_KEY] = 0
        q.note_request_made()
        assert _clear[q._CACHE_KEY] == 0
        del _clear[q._CACHE_KEY]
        q.note_request_made()   # must not raise


class TestTheReserve:
    def test_the_reserve_is_below_the_free_tier_but_not_trivial(self):
        assert 0 < q._DEFAULT_RESERVE < 1000
        assert q._CACHE_TTL <= 3600, "a stale quota view must not outlive an hour"
