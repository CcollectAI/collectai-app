"""Scrape.do monthly request quota — metered against Scrape.do's own count.

WHY THIS EXISTS (2026-08-31)
----------------------------------------------------------------------------
The free tier is **1,000 requests a month**, and nothing enforced it.

`spend_tracker` looks like it does and does not: it compares `total_spent`
against ONE shared €150 monthly pool across every provider, and scrapedo is
priced at €0.001/call. The whole 1,000-request quota is €1, so that budget
would never block before Scrape.do's hard cap was gone. Its state is also
in-memory, so a bake restart zeroes the count while the real quota keeps
counting.

`scrapedo_caller` has only a failure-based circuit breaker, which trips on
errors rather than on spend — by which point the month is over.

THE SOURCE OF TRUTH IS THEIRS, NOT OURS
----------------------------------------------------------------------------
`GET https://api.scrape.do/info` returns `RemainingMonthlyRequest`. A local
counter is a *belief* that resets on deploy; theirs is the fact, and it
survives everything. Verified empirically 2026-08-31: calling `/info` did NOT
decrement the quota (it read 1000/1000 immediately after the call), so metering
this way is free.

FAILURE BEHAVIOUR, CHOSEN DELIBERATELY
----------------------------------------------------------------------------
A stale cached value is reused when `/info` is unreachable. With no value at
all we **block** and log at ERROR. Scrape.do calls are optional enrichment: a
missed comp costs one row, while failing open against a hard cap silently burns
a month. "We could not ask" must never read as "plenty left" —
learning_a_blind_source_deletes_the_finding_not_just_the_number.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.cache import cache_get, cache_set
from app.config import SCRAPEDO_API_KEY

logger = logging.getLogger(__name__)

_INFO_URL = "https://api.scrape.do/info"
_CACHE_KEY = "scrapedo:remaining"
# 15 min: short enough that a burst is noticed within the same scrape cycle,
# long enough that metering costs one request per cycle rather than per call.
_CACHE_TTL = 900
# Kept BELOW the real 1,000 on purpose. Our view of the count is at most
# _CACHE_TTL stale, so the reserve is what absorbs the calls made inside that
# window. Stopping exactly at 0 would mean discovering the overrun from a 429.
_DEFAULT_RESERVE = 100


async def fetch_remaining(timeout: float = 15.0) -> Optional[int]:
    """Ask Scrape.do how many requests are left. None when it cannot be asked."""
    if not SCRAPEDO_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(_INFO_URL, params={"token": SCRAPEDO_API_KEY})
            r.raise_for_status()
            data = r.json()
        remaining = data.get("RemainingMonthlyRequest")
        if not isinstance(remaining, int):
            # A shape change must not read as "no quota left" OR as "plenty".
            logger.error(
                "[scrapedo_quota] /info returned no integer "
                "RemainingMonthlyRequest (got %r) — cannot meter",
                remaining,
            )
            return None
        return remaining
    except Exception as e:
        logger.warning("[scrapedo_quota] /info unreachable: %s: %s", type(e).__name__, e)
        return None


async def remaining(force: bool = False) -> Optional[int]:
    """Cached remaining count. None only when it has never been readable."""
    if not force:
        cached = cache_get(_CACHE_KEY)
        if isinstance(cached, int):
            return cached
    live = await fetch_remaining()
    if live is not None:
        cache_set(_CACHE_KEY, live, ttl=_CACHE_TTL)
        return live
    # Fall back to a STALE value rather than to nothing: an expired count is a
    # far better guide than no count, and the alternative is going dark on a
    # single flaky request.
    stale = cache_get(_CACHE_KEY)
    if isinstance(stale, int):
        logger.warning("[scrapedo_quota] using stale remaining=%d", stale)
        return stale
    return None


async def allow(reserve: int = _DEFAULT_RESERVE) -> bool:
    """Whether a Scrape.do request may be made right now."""
    left = await remaining()
    if left is None:
        logger.error(
            "[scrapedo_quota] BLOCKING: cannot read the remaining monthly quota. "
            "Failing closed — a missed comp costs one row, overrunning a hard "
            "cap costs the month."
        )
        return False
    if left <= reserve:
        logger.error(
            "[scrapedo_quota] BLOCKING: %d requests left, reserve is %d. "
            "The monthly free tier is spent; it resets on the 1st.",
            left, reserve,
        )
        return False
    return True


def note_request_made() -> None:
    """Decrement our cached view after a request, between /info refreshes.

    Without this the cached count stays flat for the full TTL and a burst
    inside that window is invisible until the next refresh — which is exactly
    what the reserve exists to absorb, but there is no reason to lean on it.
    """
    cached = cache_get(_CACHE_KEY)
    if isinstance(cached, int) and cached > 0:
        cache_set(_CACHE_KEY, cached - 1, ttl=_CACHE_TTL)
