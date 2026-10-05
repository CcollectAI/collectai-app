"""eBay Buy API daily call quota, metered against eBay's own count.

WHY THIS EXISTS (2026-10-05)
----------------------------------------------------------------------------
The Browse API allows 5,000 calls a day per application (eBay "API Call
Limits", Buy APIs). `ebay_caller` had a failure-based circuit breaker and 429
handling, and nothing that stopped a runaway loop BEFORE eBay did. This repo
has been banned for overuse once already (tcgcsv, 2026-07-31). Measured the
day this was written: ~1,500 calls/day, so 30% of the limit.

THE SOURCE OF TRUTH IS THEIRS, NOT OURS
----------------------------------------------------------------------------
Same rule as `scrapedo_quota`: a local counter resets on every bake restart
(43 restarts in one week, 2026-09). eBay's Developer Analytics API
(`GET /developer/analytics/v1_beta/rate_limit/`) returns `count`, `limit`,
`remaining` and `reset` per resource, using the same application token as
Browse. Verified 2026-10-05: buy.browse 880 / 5,000, reset daily at
07:00 UTC. We re-read it every `_REFRESH_S` and count our own calls in
between, so the view is at most one refresh stale; `_RESERVE` absorbs that.

FAILURE BEHAVIOUR, CHOSEN DELIBERATELY
----------------------------------------------------------------------------
Unlike Scrape.do, eBay Browse is core data, not optional enrichment, so a
blind meter must not shut eBay off. It must not mean "unlimited" either. With
no readable count we allow at most `_BLIND_WINDOW_CAP` calls per
`_REFRESH_S` window: 40 per 15 min is 3,840 a day even if we are blind all
day, which is below 5,000 by construction. Blindness is logged at ERROR once
per window: "we could not ask" must never read as "plenty left".
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_URL = "https://api.ebay.com/developer/analytics/v1_beta/rate_limit/"
_RESOURCE = "buy.browse"
_REFRESH_S = 900
# Stop at 4,500 of 5,000. At ~1,500/day we make ~16 calls per refresh window,
# so 500 is far more than one window's staleness needs; the rest is margin.
_RESERVE = 500
# Used only when eBay's count cannot be read: 96 windows x 40 = 3,840/day.
_BLIND_WINDOW_CAP = 40

_lock = asyncio.Lock()
_state = {
    "remaining": None,      # eBay's `remaining` at the last successful read
    "fetched_at": 0.0,      # monotonic time of that read (0 = never)
    "since_fetch": 0,       # calls we made after that read
    "window_start": 0.0,    # blind-mode window start (monotonic)
    "window_calls": 0,      # calls made in the current blind window
    "blocked_logged_at": 0.0,
}


async def fetch_remaining(client: httpx.AsyncClient, token: str) -> Optional[int]:
    """Ask eBay how many buy.browse calls are left today. None when it cannot be asked."""
    try:
        r = await client.get(
            _RATE_LIMIT_URL,
            params={"api_context": "buy", "api_name": "browse"},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        for api in r.json().get("rateLimits") or []:
            for res in api.get("resources") or []:
                if res.get("name") == _RESOURCE:
                    for rate in res.get("rates") or []:
                        remaining = rate.get("remaining")
                        if isinstance(remaining, int):
                            return remaining
        # A shape change must not read as "no quota" OR as "plenty".
        logger.error("[ebay_quota] rate_limit response has no %s.remaining", _RESOURCE)
        return None
    except Exception as e:
        logger.warning("[ebay_quota] rate_limit unreachable: %s: %s", type(e).__name__, e)
        return None


async def allow_call(client: httpx.AsyncClient, token: str) -> bool:
    """True when one more Browse call stays inside the daily budget.

    Call it immediately before each Browse request, then `record_call()` once
    the request has actually been sent.
    """
    now = time.monotonic()
    async with _lock:
        if not _state["fetched_at"] or now - _state["fetched_at"] >= _REFRESH_S:
            remaining = await fetch_remaining(client, token)
            _state["fetched_at"] = now
            _state["since_fetch"] = 0
            _state["remaining"] = remaining

        if _state["remaining"] is not None:
            left = _state["remaining"] - _state["since_fetch"]
            if left > _RESERVE:
                return True
            if now - _state["blocked_logged_at"] >= _REFRESH_S:
                _state["blocked_logged_at"] = now
                logger.error(
                    "[ebay_quota] daily budget reached: eBay reports %d left, %d used "
                    "since, reserve %d. Browse calls are skipped until eBay's daily "
                    "reset (07:00 UTC).",
                    _state["remaining"], _state["since_fetch"], _RESERVE,
                )
            return False

        # Blind: eBay's count is unreadable. Bounded, not open.
        if now - _state["window_start"] >= _REFRESH_S:
            _state["window_start"] = now
            _state["window_calls"] = 0
            logger.error(
                "[ebay_quota] cannot read eBay's call count; allowing at most %d "
                "Browse calls in the next %d s",
                _BLIND_WINDOW_CAP, _REFRESH_S,
            )
        return _state["window_calls"] < _BLIND_WINDOW_CAP


def record_call() -> None:
    """Count one Browse request that was actually sent."""
    _state["since_fetch"] += 1
    _state["window_calls"] += 1


def snapshot() -> dict:
    """Current meter state, for logs and health endpoints."""
    return dict(_state)
