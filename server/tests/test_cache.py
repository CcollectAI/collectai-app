"""Tests for app.cache — pluggable cache backends (InMemory + Redis adapter)."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.cache as cache_mod
from app.cache import (
    CacheBackend,
    InMemoryCache,
    RedisCache,
    cache_clear,
    cache_delete,
    cache_get,
    cache_set,
    cache_stats,
    create_cache,
    get_backend,
    reset_backend,
    ttl_cache,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    """Reset cache state before each test."""
    reset_backend(None)
    # Ensure an InMemoryCache is the default for every test
    backend = get_backend()
    assert isinstance(backend, InMemoryCache)
    yield
    reset_backend(None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backend() -> InMemoryCache:
    b = get_backend()
    assert isinstance(b, InMemoryCache)
    return b


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
        cache_set("expiring", "value", ttl=1)
        real_time = time.monotonic()
        with patch("app.cache.time.monotonic", return_value=real_time + 2):
            result = cache_get("expiring")
        assert result is None
        # Entry should have been evicted
        assert "expiring" not in _backend()._store

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


# ---------------------------------------------------------------------------
# InMemoryCache class (direct)
# ---------------------------------------------------------------------------


class TestInMemoryCache:
    @pytest.mark.asyncio
    async def test_get_set_delete(self):
        cache = InMemoryCache()
        await cache.set("k", "v", ttl=60)
        assert await cache.get("k") == "v"
        await cache.delete("k")
        assert await cache.get("k") is None

    @pytest.mark.asyncio
    async def test_clear(self):
        cache = InMemoryCache()
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.get("a") is None

    @pytest.mark.asyncio
    async def test_stats(self):
        cache = InMemoryCache()
        await cache.set("x", 10)
        await cache.get("x")  # hit
        await cache.get("y")  # miss
        stats = await cache.stats()
        assert stats == {"hits": 1, "misses": 1, "size": 1}

    def test_cleanup_removes_expired(self):
        cache = InMemoryCache()
        # Manually insert an expired entry
        cache._store["old"] = ("val", time.monotonic() - 10)
        cache._store["fresh"] = ("val", time.monotonic() + 300)
        evicted = cache.cleanup()
        assert evicted == 1
        assert "old" not in cache._store
        assert "fresh" in cache._store

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        cache = InMemoryCache()
        await cache.set("temp", "data", ttl=1)
        real_time = time.monotonic()
        with patch("app.cache.time.monotonic", return_value=real_time + 2):
            assert await cache.get("temp") is None


# ---------------------------------------------------------------------------
# RedisCache class (mocked)
# ---------------------------------------------------------------------------


class TestRedisCache:
    def _make_mock_client(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=None)
        client.setex = AsyncMock()
        client.delete = AsyncMock()
        client.scan = AsyncMock(return_value=(0, []))
        client.dbsize = AsyncMock(return_value=0)
        client.ping = AsyncMock(return_value=True)
        client.aclose = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_miss(self):
        client = self._make_mock_client()
        cache = RedisCache(client)
        result = await cache.get("missing")
        assert result is None
        client.get.assert_awaited_once_with("collectai:missing")

    @pytest.mark.asyncio
    async def test_get_hit(self):
        client = self._make_mock_client()
        client.get.return_value = json.dumps({"price": 42})
        cache = RedisCache(client)
        result = await cache.get("item")
        assert result == {"price": 42}
        stats = await cache.stats()
        assert stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_set_calls_setex(self):
        client = self._make_mock_client()
        cache = RedisCache(client)
        await cache.set("k", {"a": 1}, ttl=120)
        client.setex.assert_awaited_once_with(
            "collectai:k", 120, json.dumps({"a": 1})
        )

    @pytest.mark.asyncio
    async def test_delete(self):
        client = self._make_mock_client()
        cache = RedisCache(client)
        await cache.delete("k")
        client.delete.assert_awaited_once_with("collectai:k")

    @pytest.mark.asyncio
    async def test_clear_uses_scan(self):
        client = self._make_mock_client()
        client.scan.return_value = (0, ["collectai:a", "collectai:b"])
        cache = RedisCache(client)
        await cache.clear()
        client.scan.assert_awaited()
        client.delete.assert_awaited_once_with("collectai:a", "collectai:b")

    @pytest.mark.asyncio
    async def test_ping_success(self):
        client = self._make_mock_client()
        cache = RedisCache(client)
        assert await cache.ping() is True

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        client = self._make_mock_client()
        client.ping.side_effect = ConnectionError("refused")
        cache = RedisCache(client)
        assert await cache.ping() is False

    @pytest.mark.asyncio
    async def test_get_handles_connection_error(self):
        client = self._make_mock_client()
        client.get.side_effect = ConnectionError("refused")
        cache = RedisCache(client)
        result = await cache.get("k")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_handles_connection_error(self):
        client = self._make_mock_client()
        client.setex.side_effect = ConnectionError("refused")
        cache = RedisCache(client)
        # Should not raise
        await cache.set("k", "v")

    @pytest.mark.asyncio
    async def test_get_handles_bad_json(self):
        client = self._make_mock_client()
        client.get.return_value = "not-valid-json{{"
        cache = RedisCache(client)
        result = await cache.get("k")
        assert result is None

    @pytest.mark.asyncio
    async def test_close(self):
        client = self._make_mock_client()
        cache = RedisCache(client)
        await cache.close()
        client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_key_prefix(self):
        client = self._make_mock_client()
        cache = RedisCache(client)
        assert cache._prefixed("foo") == "collectai:foo"


# ---------------------------------------------------------------------------
# Factory (create_cache)
# ---------------------------------------------------------------------------


class TestCreateCache:
    @pytest.mark.asyncio
    async def test_no_redis_url_returns_inmemory(self):
        reset_backend(None)
        backend = await create_cache(redis_url=None)
        assert isinstance(backend, InMemoryCache)

    @pytest.mark.asyncio
    async def test_redis_url_without_library_returns_inmemory(self):
        reset_backend(None)
        with patch.object(cache_mod, "HAS_REDIS", False):
            backend = await create_cache(redis_url="redis://localhost:6379")
        assert isinstance(backend, InMemoryCache)

    @pytest.mark.asyncio
    async def test_redis_connection_failure_falls_back(self):
        reset_backend(None)
        with patch.object(cache_mod, "HAS_REDIS", True):
            mock_from_url = MagicMock()
            mock_client = AsyncMock()
            mock_client.ping.side_effect = ConnectionError("refused")
            mock_from_url.return_value = mock_client
            with patch.object(cache_mod, "aioredis") as mock_redis_mod:
                mock_redis_mod.from_url = mock_from_url
                backend = await create_cache(redis_url="redis://localhost:6379")
        assert isinstance(backend, InMemoryCache)

    @pytest.mark.asyncio
    async def test_returns_existing_backend(self):
        """Calling create_cache twice returns the same instance."""
        reset_backend(None)
        b1 = await create_cache(redis_url=None)
        b2 = await create_cache(redis_url=None)
        assert b1 is b2

    @pytest.mark.asyncio
    async def test_redis_success_returns_redis_cache(self):
        reset_backend(None)
        with patch.object(cache_mod, "HAS_REDIS", True):
            mock_from_url = MagicMock()
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_client
            with patch.object(cache_mod, "aioredis") as mock_redis_mod:
                mock_redis_mod.from_url = mock_from_url
                backend = await create_cache(redis_url="redis://localhost:6379")
        assert isinstance(backend, RedisCache)


# ---------------------------------------------------------------------------
# reset_backend / get_backend
# ---------------------------------------------------------------------------


class TestBackendManagement:
    def test_get_backend_creates_inmemory_if_none(self):
        reset_backend(None)
        b = get_backend()
        assert isinstance(b, InMemoryCache)

    def test_reset_backend(self):
        new = InMemoryCache()
        reset_backend(new)
        assert get_backend() is new

    def test_reset_to_none(self):
        reset_backend(None)
        # get_backend should auto-create a new one
        b = get_backend()
        assert isinstance(b, InMemoryCache)
