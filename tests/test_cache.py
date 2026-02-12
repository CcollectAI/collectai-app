"""Tests for app.cache — in-memory TTL cache."""

import time
from unittest.mock import patch

import pytest

import app.cache as cache_mod
from app.cache import (
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cache_stats,
    ttl_cache,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    """Reset cache state before each test."""
    cache_mod._store.clear()
    cache_mod._hits = 0
    cache_mod._misses = 0
    yield
    cache_mod._store.clear()
    cache_mod._hits = 0
    cache_mod._misses = 0


# ---------------------------------------------------------------------------
# cache_get / cache_set
# ---------------------------------------------------------------------------

class TestCacheGetSet:
    def test_get_missing_key_returns_none(self):
        assert cache_get("nonexistent") is None

    def test_set_and_get(self):
        cache_set("key1", {"price": 42.0})
        assert cache_get("key1") == {"price": 42.0}

    def test_set_overwrites(self):
        cache_set("key1", "old")
        cache_set("key1", "new")
        assert cache_get("key1") == "new"

    def test_different_value_types(self):
        cache_set("str", "hello")
        cache_set("int", 42)
        cache_set("list", [1, 2, 3])
        cache_set("none_val", None)  # None is a valid cached value... but cache_get returns None for miss

        assert cache_get("str") == "hello"
        assert cache_get("int") == 42
        assert cache_get("list") == [1, 2, 3]

    def test_expired_entry_returns_none(self):
        """An entry past its TTL should return None and be evicted."""
        # Insert with TTL=0 effectively: set expiry in the past
        cache_set("expiring", "value", ttl=1)
        # Patch monotonic to simulate time passing
        real_time = time.monotonic()
        with patch("app.cache.time.monotonic", return_value=real_time + 2):
            result = cache_get("expiring")
        assert result is None
        # Entry should have been evicted
        assert "expiring" not in cache_mod._store

    def test_not_yet_expired_returns_value(self):
        cache_set("fresh", "value", ttl=300)
        assert cache_get("fresh") == "value"


# ---------------------------------------------------------------------------
# cache_delete
# ---------------------------------------------------------------------------

class TestCacheDelete:
    def test_delete_existing_key(self):
        cache_set("key1", "val")
        cache_delete("key1")
        assert cache_get("key1") is None

    def test_delete_nonexistent_key_no_error(self):
        cache_delete("nonexistent")  # should not raise


# ---------------------------------------------------------------------------
# cache_clear
# ---------------------------------------------------------------------------

class TestCacheClear:
    def test_clear_removes_all(self):
        cache_set("a", 1)
        cache_set("b", 2)
        cache_set("c", 3)
        cache_clear()
        assert cache_get("a") is None
        assert cache_get("b") is None
        assert cache_get("c") is None

    def test_clear_empty_cache_no_error(self):
        cache_clear()  # should not raise


# ---------------------------------------------------------------------------
# cache_stats
# ---------------------------------------------------------------------------

class TestCacheStats:
    def test_initial_stats(self):
        stats = cache_stats()
        assert stats == {"hits": 0, "misses": 0, "size": 0}

    def test_miss_increments(self):
        cache_get("nope")
        cache_get("nope2")
        stats = cache_stats()
        assert stats["misses"] == 2
        assert stats["hits"] == 0

    def test_hit_increments(self):
        cache_set("key", "val")
        cache_get("key")
        cache_get("key")
        stats = cache_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 0

    def test_size_tracks_entries(self):
        cache_set("a", 1)
        cache_set("b", 2)
        assert cache_stats()["size"] == 2
        cache_delete("a")
        assert cache_stats()["size"] == 1

    def test_expired_entry_counts_as_miss(self):
        cache_set("temp", "val", ttl=1)
        real_time = time.monotonic()
        with patch("app.cache.time.monotonic", return_value=real_time + 2):
            cache_get("temp")
        stats = cache_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0


# ---------------------------------------------------------------------------
# ttl_cache decorator
# ---------------------------------------------------------------------------

class TestTtlCacheDecorator:
    @pytest.mark.asyncio
    async def test_caches_result(self):
        call_count = 0

        @ttl_cache(seconds=300)
        async def my_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await my_func(5)
        result2 = await my_func(5)
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # second call served from cache

    @pytest.mark.asyncio
    async def test_different_args_different_cache(self):
        call_count = 0

        @ttl_cache(seconds=300)
        async def square(n):
            nonlocal call_count
            call_count += 1
            return n ** 2

        assert await square(3) == 9
        assert await square(4) == 16
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_ttl_expiry_refetches(self):
        call_count = 0

        @ttl_cache(seconds=10)
        async def fetch_data(key):
            nonlocal call_count
            call_count += 1
            return f"data-{call_count}"

        result1 = await fetch_data("a")
        assert result1 == "data-1"

        # Simulate TTL expiry
        real_time = time.monotonic()
        with patch("app.cache.time.monotonic", return_value=real_time + 20):
            result2 = await fetch_data("a")

        assert result2 == "data-2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_custom_key_prefix(self):
        @ttl_cache(seconds=300, key_prefix="custom")
        async def my_func(x):
            return x

        await my_func("hello")
        # Should be stored under "custom:hello"
        assert cache_get("custom:hello") == "hello"

    @pytest.mark.asyncio
    async def test_default_key_prefix_is_func_name(self):
        @ttl_cache(seconds=300)
        async def named_func(x):
            return x + 1

        await named_func(10)
        assert cache_get("named_func:10") == 11

    @pytest.mark.asyncio
    async def test_kwargs_in_cache_key(self):
        @ttl_cache(seconds=300)
        async def kw_func(a, b=0):
            return a + b

        result = await kw_func(1, b=2)
        assert result == 3
        # Cache key should include kwargs
        assert cache_get("kw_func:1:b=2") == 3

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @ttl_cache(seconds=60)
        async def original_name():
            return 42

        assert original_name.__name__ == "original_name"
