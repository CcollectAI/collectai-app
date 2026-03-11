"""
Cache layer with pluggable backends (in-memory or Redis).

When ``REDIS_URL`` is set, the module connects to Redis asynchronously via
``redis.asyncio`` and serialises values as JSON.  When Redis is unavailable
(env var unset, library not installed, or connection failure) the module falls
back to a lightweight in-memory dict with per-entry TTL.

The public surface stays the same — import the module-level helpers:

    from app.cache import cache_get, cache_set, cache_delete, cache_clear
    from app.cache import cache_stats, ttl_cache

Or access the backend singleton directly via ``get_backend()``.
"""

from __future__ import annotations

import abc
import asyncio
import functools
import json
import logging
import time
from typing import Any

from app.config import CACHE_TTL, REDIS_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional redis import
# ---------------------------------------------------------------------------

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]
    HAS_REDIS = False


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class CacheBackend(abc.ABC):
    """Protocol every cache backend must implement."""

    @abc.abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return the cached value for *key*, or ``None`` on miss/expiry."""

    @abc.abstractmethod
    async def set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> None:
        """Store *value* under *key* with a TTL in seconds."""

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a single key."""

    @abc.abstractmethod
    async def clear(self) -> None:
        """Remove **all** keys managed by this backend."""

    @abc.abstractmethod
    async def stats(self) -> dict[str, int]:
        """Return ``{"hits": …, "misses": …, "size": …}``."""


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------


class InMemoryCache(CacheBackend):
    """Dict-based cache with per-entry TTL (single-process only)."""

    _CLEANUP_INTERVAL: int = 100

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._set_counter: int = 0

    # -- CacheBackend interface --

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    async def set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> None:
        self._store[key] = (value, time.monotonic() + ttl)
        self._set_counter += 1
        if self._set_counter >= self._CLEANUP_INTERVAL:
            self._set_counter = 0
            self.cleanup()

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()

    async def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}

    # -- Extras --

    def cleanup(self) -> int:
        """Remove all expired entries and return the number evicted."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
        return len(expired)


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class RedisCache(CacheBackend):
    """Async Redis-backed cache.  Values are JSON-serialised."""

    _KEY_PREFIX = "collectai:"

    def __init__(self, client: "aioredis.Redis") -> None:  # type: ignore[name-defined]
        self._client = client
        self._hits: int = 0
        self._misses: int = 0

    # -- CacheBackend interface --

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(self._prefixed(key))
        except Exception:
            logger.warning("Redis GET failed for key=%s, returning None", key, exc_info=True)
            self._misses += 1
            return None
        if raw is None:
            self._misses += 1
            return None
        self._hits += 1
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Redis: could not deserialise value for key=%s", key)
            self._misses += 1
            self._hits -= 1  # undo the premature hit
            return None

    async def set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> None:
        try:
            serialised = json.dumps(value)
            await self._client.setex(self._prefixed(key), ttl, serialised)
        except Exception:
            logger.warning("Redis SET failed for key=%s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(self._prefixed(key))
        except Exception:
            logger.warning("Redis DELETE failed for key=%s", key, exc_info=True)

    async def clear(self) -> None:
        """Delete all keys with the CollectAI prefix.

        Uses SCAN to avoid blocking the server on large keyspaces.
        """
        try:
            cursor: int | bytes = 0
            while True:
                cursor, keys = await self._client.scan(
                    cursor=cursor, match=f"{self._KEY_PREFIX}*", count=500
                )
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            logger.warning("Redis CLEAR (scan+delete) failed", exc_info=True)

    async def stats(self) -> dict[str, int]:
        size = 0
        try:
            # dbsize is server-wide; for a more accurate count we'd scan,
            # but this is cheap and good enough for the ops endpoint.
            size = await self._client.dbsize()
        except Exception:
            pass
        return {"hits": self._hits, "misses": self._misses, "size": size}

    # -- Extras --

    async def ping(self) -> bool:
        """Return True if the Redis server is reachable."""
        try:
            return await self._client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """Gracefully close the underlying connection pool."""
        try:
            await self._client.aclose()
        except Exception:
            pass

    # -- Helpers --

    def _prefixed(self, key: str) -> str:
        return f"{self._KEY_PREFIX}{key}"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_backend: CacheBackend | None = None


async def create_cache(redis_url: str | None = REDIS_URL) -> CacheBackend:
    """Create (or return the existing) cache backend.

    * If *redis_url* is set and the ``redis`` package is installed, try to
      connect.  If the connection succeeds, return a ``RedisCache``.
    * Otherwise fall back to ``InMemoryCache``.
    """
    global _backend
    if _backend is not None:
        return _backend

    if redis_url and HAS_REDIS:
        try:
            client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await client.ping()
            _backend = RedisCache(client)
            logger.info("Cache backend: Redis (%s)", redis_url.split("@")[-1])
            return _backend
        except Exception:
            logger.warning(
                "Could not connect to Redis at %s — falling back to in-memory cache",
                redis_url.split("@")[-1],
                exc_info=True,
            )

    _backend = InMemoryCache()
    logger.info("Cache backend: InMemory")
    return _backend


def get_backend() -> CacheBackend:
    """Return the current backend, creating an InMemoryCache if none exists yet.

    This is a synchronous accessor for use in sync helpers (``cache_get`` etc.).
    If the async ``create_cache()`` hasn't been called yet (e.g. during tests
    or before app startup), an ``InMemoryCache`` is created automatically.
    """
    global _backend
    if _backend is None:
        _backend = InMemoryCache()
    return _backend


def reset_backend(backend: CacheBackend | None = None) -> None:
    """Replace the active backend (mainly useful in tests)."""
    global _backend
    _backend = backend


# ---------------------------------------------------------------------------
# Convenience wrappers (backward-compatible, synchronous API)
# ---------------------------------------------------------------------------
# The original module exposed synchronous functions.  All downstream callers
# use these from synchronous code, so we keep the same signatures.  Under the
# hood we check if there's a running event loop and schedule the async call;
# for the InMemoryCache path this is effectively free because the async
# methods don't actually await anything.

# Stats counters used by the synchronous wrappers when the backend is
# InMemoryCache (to keep the same semantics as the original module).
_hits = 0
_misses = 0

# Expose _store for tests that reach into internals
_store: dict[str, tuple[Any, float]] = {}


def _sync_get_store() -> dict[str, tuple[Any, float]]:
    """Return the internal store of the InMemoryCache backend (test helper)."""
    b = get_backend()
    if isinstance(b, InMemoryCache):
        return b._store
    return _store


def cache_get(key: str) -> Any | None:
    """Get a value from cache.  Returns None if missing or expired."""
    b = get_backend()
    if isinstance(b, InMemoryCache):
        # Fast synchronous path — avoid event-loop overhead.
        entry = b._store.get(key)
        if entry is None:
            b._misses += 1
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del b._store[key]
            b._misses += 1
            return None
        b._hits += 1
        return value
    # Redis path — must go through async.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # We're inside an async context but called synchronously.
        # Return a coroutine that the caller should await — but for backward
        # compat, schedule and wait via a new thread.  This is a rare path.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, b.get(key)).result()
    return asyncio.run(b.get(key))


def cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    """Set a value in cache with TTL in seconds."""
    b = get_backend()
    if isinstance(b, InMemoryCache):
        b._store[key] = (value, time.monotonic() + ttl)
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, b.set(key, value, ttl)).result()
    else:
        asyncio.run(b.set(key, value, ttl))


def cache_delete(key: str) -> None:
    """Remove a key from cache."""
    b = get_backend()
    if isinstance(b, InMemoryCache):
        b._store.pop(key, None)
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, b.delete(key)).result()
    else:
        asyncio.run(b.delete(key))


def cache_clear() -> None:
    """Clear all cached entries."""
    b = get_backend()
    if isinstance(b, InMemoryCache):
        b._store.clear()
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, b.clear()).result()
    else:
        asyncio.run(b.clear())


def cache_stats() -> dict[str, int]:
    """Return cache hit/miss stats."""
    b = get_backend()
    if isinstance(b, InMemoryCache):
        return {"hits": b._hits, "misses": b._misses, "size": len(b._store)}
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, b.stats()).result()
    return asyncio.run(b.stats())


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def ttl_cache(seconds: int = CACHE_TTL, key_prefix: str = ""):
    """
    Decorator for caching async function results with TTL.

    Builds cache key from function name + args.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            prefix = key_prefix or func.__name__
            cache_key = f"{prefix}:" + ":".join(str(a) for a in args)
            if kwargs:
                cache_key += ":" + ":".join(
                    f"{k}={v}" for k, v in sorted(kwargs.items())
                )

            cached = cache_get(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            cache_set(cache_key, result, ttl=seconds)
            return result

        return wrapper

    return decorator
