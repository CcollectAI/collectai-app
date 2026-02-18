"""
In-memory TTL cache for expensive or rarely-changing responses.

Usage:
    from app.cache import ttl_cache

    @ttl_cache(seconds=300)
    async def get_price_evidence(item_id: str) -> dict:
        ...

    # Or use the cache directly:
    from app.cache import cache_get, cache_set

    cached = cache_get("barcode:978123456")
    if cached is not None:
        return cached
    result = await expensive_lookup()
    cache_set("barcode:978123456", result, ttl=86400)
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Store: {key: (value, expires_at)}
_store: dict[str, tuple[Any, float]] = {}

# Stats
_hits = 0
_misses = 0


def cache_get(key: str) -> Any | None:
    """Get a value from cache. Returns None if missing or expired."""
    global _hits, _misses
    entry = _store.get(key)
    if entry is None:
        _misses += 1
        return None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        del _store[key]
        _misses += 1
        return None
    _hits += 1
    return value


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set a value in cache with TTL in seconds."""
    _store[key] = (value, time.monotonic() + ttl)


def cache_delete(key: str) -> None:
    """Remove a key from cache."""
    _store.pop(key, None)


def cache_clear() -> None:
    """Clear all cached entries."""
    _store.clear()


def cache_stats() -> dict[str, int]:
    """Return cache hit/miss stats."""
    return {"hits": _hits, "misses": _misses, "size": len(_store)}


def ttl_cache(seconds: int = 300, key_prefix: str = ""):
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
                cache_key += ":" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

            cached = cache_get(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            cache_set(cache_key, result, ttl=seconds)
            return result

        return wrapper
    return decorator
