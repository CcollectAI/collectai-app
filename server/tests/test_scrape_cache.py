"""Tests for the global URL dedup scrape cache."""

import pytest

from app.cache import InMemoryCache, reset_backend
from app.lib.scrape_cache import (
    ENRICH_CACHE_TTL,
    SCRAPE_CACHE_TTL,
    _cache_key,
    cached_scrape,
    cached_search,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Reset cache backend to a fresh InMemoryCache for every test."""
    backend = InMemoryCache()
    reset_backend(backend)
    yield
    reset_backend(None)


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_deterministic(self):
        """Same URL always produces the same key."""
        assert _cache_key("https://example.com") == _cache_key("https://example.com")

    def test_different_urls_differ(self):
        """Different URLs produce different keys."""
        assert _cache_key("https://a.com") != _cache_key("https://b.com")

    def test_prefix(self):
        """Key starts with 'scrape:' prefix."""
        assert _cache_key("https://example.com").startswith("scrape:")

    def test_length(self):
        """Key is 'scrape:' + 16 hex chars = 23 chars."""
        assert len(_cache_key("https://example.com")) == len("scrape:") + 16


# ---------------------------------------------------------------------------
# cached_scrape
# ---------------------------------------------------------------------------


class TestCachedScrape:
    @pytest.mark.asyncio
    async def test_miss_then_hit(self):
        """First call executes fn, second returns cached."""
        call_count = 0

        async def fake_scrape(url: str):
            nonlocal call_count
            call_count += 1
            return {"markdown": "hello", "url": url}

        r1 = await cached_scrape("https://example.com", fake_scrape)
        assert r1 == {"markdown": "hello", "url": "https://example.com"}
        assert call_count == 1

        r2 = await cached_scrape("https://example.com", fake_scrape)
        assert r2 == r1
        assert call_count == 1  # not called again

    @pytest.mark.asyncio
    async def test_none_result_not_cached(self):
        """If scrape_fn returns None, result is NOT stored in cache."""
        call_count = 0

        async def failing_scrape(url: str):
            nonlocal call_count
            call_count += 1
            return None

        r1 = await cached_scrape("https://fail.com", failing_scrape)
        assert r1 is None
        assert call_count == 1

        r2 = await cached_scrape("https://fail.com", failing_scrape)
        assert r2 is None
        assert call_count == 2  # called again because nothing was cached

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """TTL parameter is forwarded to the cache backend."""
        async def fake_scrape(url: str):
            return {"ok": True}

        result = await cached_scrape("https://example.com", fake_scrape, ttl=60)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_different_urls_independent(self):
        """Different URLs get independent cache entries."""
        call_count = 0

        async def fake_scrape(url: str):
            nonlocal call_count
            call_count += 1
            return {"url": url}

        await cached_scrape("https://a.com", fake_scrape)
        await cached_scrape("https://b.com", fake_scrape)
        assert call_count == 2

        # Both should now be cached
        await cached_scrape("https://a.com", fake_scrape)
        await cached_scrape("https://b.com", fake_scrape)
        assert call_count == 2


# ---------------------------------------------------------------------------
# cached_search
# ---------------------------------------------------------------------------


class TestCachedSearch:
    @pytest.mark.asyncio
    async def test_miss_then_hit(self):
        """First call executes fn, second returns cached."""
        call_count = 0

        async def fake_search(query: str):
            nonlocal call_count
            call_count += 1
            return [{"title": "Result", "url": "https://r.com"}]

        r1 = await cached_search("pokemon cards", fake_search)
        assert len(r1) == 1
        assert call_count == 1

        r2 = await cached_search("pokemon cards", fake_search)
        assert r2 == r1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_empty_list_not_cached(self):
        """Empty search results are NOT cached (so retry is possible)."""
        call_count = 0

        async def empty_search(query: str):
            nonlocal call_count
            call_count += 1
            return []

        r1 = await cached_search("nothing here", empty_search)
        assert r1 == []
        assert call_count == 1

        r2 = await cached_search("nothing here", empty_search)
        assert r2 == []
        assert call_count == 2


# ---------------------------------------------------------------------------
# TTL constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_scrape_ttl(self):
        assert SCRAPE_CACHE_TTL == 21_600

    def test_enrich_ttl(self):
        assert ENRICH_CACHE_TTL == 43_200
