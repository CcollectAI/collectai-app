"""
Global URL deduplication cache for web scraping.

Prevents re-scraping the same URL within a configurable time window by keying
on SHA-256(url) and storing the result in the existing cache backend
(InMemoryCache or Redis).

TTLs:
    SCRAPE_CACHE_TTL  = 21 600 s (6 hours)  -- marketplace search results
    ENRICH_CACHE_TTL  = 43 200 s (12 hours)  -- enrichment / detail scrapes

Usage in scrape clients:

    from app.lib.scrape_cache import cached_scrape, ENRICH_CACHE_TTL

    result = await cached_scrape(url, lambda u: _real_scrape(u), ttl=ENRICH_CACHE_TTL)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Awaitable, Callable, Optional

from app.cache import get_backend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL constants
# ---------------------------------------------------------------------------

SCRAPE_CACHE_TTL: int = 21_600  # 6 hours for search / marketplace results
ENRICH_CACHE_TTL: int = 43_200  # 12 hours for enrichment detail pages

# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------


def _cache_key(url: str) -> str:
    """Deterministic cache key from a URL (SHA-256, truncated to 16 hex chars)."""
    return f"scrape:{hashlib.sha256(url.encode()).hexdigest()[:16]}"


async def cached_scrape(
    url: str,
    scrape_fn: Callable[[str], Awaitable[Optional[dict[str, Any]]]],
    *,
    ttl: int = SCRAPE_CACHE_TTL,
) -> Optional[dict[str, Any]]:
    """Cache wrapper for any async scrape function.

    1. Checks the cache for a previous result keyed on SHA-256(url).
    2. On HIT, returns the cached value immediately.
    3. On MISS, calls ``scrape_fn(url)``, stores a successful result, and
       returns it.

    Args:
        url: The URL to scrape.
        scrape_fn: Async callable that accepts a URL and returns a dict or None.
        ttl: Time-to-live in seconds (default: 6 hours).

    Returns:
        The scrape result dict, or ``None`` on failure.
    """
    key = _cache_key(url)
    backend = get_backend()

    # --- Check cache ---
    cached = await backend.get(key)
    if cached is not None:
        logger.debug("[scrape_cache] HIT  %s", url[:80])
        return cached

    # --- Execute scrape ---
    result = await scrape_fn(url)

    # --- Store on success ---
    if result:
        await backend.set(key, result, ttl=ttl)
        logger.debug("[scrape_cache] STORED %s (ttl=%ds)", url[:80], ttl)

    return result


async def cached_search(
    query: str,
    search_fn: Callable[[str], Awaitable[list[dict[str, Any]]]],
    *,
    ttl: int = SCRAPE_CACHE_TTL,
) -> list[dict[str, Any]]:
    """Cache wrapper for search functions that return a list of results.

    Keyed on SHA-256 of the query string.  Returns an empty list on cache miss
    when the search itself returns an empty list (not cached in that case).
    """
    key = f"search:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
    backend = get_backend()

    cached = await backend.get(key)
    if cached is not None:
        logger.debug("[scrape_cache] SEARCH HIT  '%s'", query[:80])
        return cached

    results = await search_fn(query)

    if results:
        await backend.set(key, results, ttl=ttl)
        logger.debug("[scrape_cache] SEARCH STORED '%s' (%d results, ttl=%ds)", query[:80], len(results), ttl)

    return results
