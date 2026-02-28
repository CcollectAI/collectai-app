"""
Sliding-window rate limiting middleware and per-user rate limit dependency.

Global middleware limits requests per IP using an in-memory counter with a
configurable window (default: 60 requests per minute).

Per-user rate limits use a sliding-window counter keyed by ``user_id``
(extracted from the JWT).  Use ``per_user_rate_limit(max_requests, window)``
to create a FastAPI ``Depends()`` callable for expensive endpoints.

Configure via environment variables:
    RATE_LIMIT_RPM=60        # requests per minute per IP
    RATE_LIMIT_ENABLED=true  # set to false to disable
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from typing import Callable, Awaitable

from fastapi import Depends
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth import get_current_user_id
from app.config import (
    RATE_LIMIT_RPM as _CFG_RATE_LIMIT_RPM,
    RATE_LIMIT_ENABLED as _CFG_RATE_LIMIT_ENABLED,
    PER_USER_RATE_LIMIT_ENABLED as _CFG_PER_USER_RATE_LIMIT_ENABLED,
)

logger = logging.getLogger(__name__)

# Module-level mutable copies so tests can monkey-patch them
RATE_LIMIT_RPM = _CFG_RATE_LIMIT_RPM
RATE_LIMIT_ENABLED = _CFG_RATE_LIMIT_ENABLED
PER_USER_RATE_LIMIT_ENABLED = _CFG_PER_USER_RATE_LIMIT_ENABLED
WINDOW_SECONDS = 60

# Exempt paths that should never be rate-limited
EXEMPT_PATHS = frozenset({"/healthz", "/version", "/ops/status"})

# In-memory sliding window: {ip: [timestamp, ...]}
_hits: dict[str, list[float]] = defaultdict(list)
_last_eviction: float = 0.0  # monotonic timestamp of last key eviction
_EVICTION_INTERVAL: float = 300.0  # evict stale keys every 5 minutes


def _client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(timestamps: list[float], now: float) -> list[float]:
    """Remove timestamps older than the window."""
    cutoff = now - WINDOW_SECONDS
    return [t for t in timestamps if t > cutoff]


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    Sliding-window rate limiter.

    Returns 429 Too Many Requests when the per-IP limit is exceeded.
    """
    if not RATE_LIMIT_ENABLED:
        return await call_next(request)

    path = request.url.path
    if path in EXEMPT_PATHS:
        return await call_next(request)

    ip = _client_ip(request)
    now = time.monotonic()

    # Prune old entries and check limit
    _hits[ip] = _prune(_hits[ip], now)

    if len(_hits[ip]) >= RATE_LIMIT_RPM:
        logger.warning("Rate limit exceeded for %s on %s", ip, path)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later.", "code": "RATE_LIMITED"},
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )

    _hits[ip].append(now)

    # Periodically evict empty keys to prevent unbounded memory growth
    global _last_eviction
    if now - _last_eviction > _EVICTION_INTERVAL:
        _last_eviction = now
        stale = [k for k, v in _hits.items() if not v]
        for k in stale:
            del _hits[k]
        if stale:
            logger.debug("Evicted %d stale IP keys from rate limiter", len(stale))

    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Per-user sliding-window rate limit (FastAPI dependency)
# ---------------------------------------------------------------------------

# Shared store across all per-user limiters: {(scope, user_id): [timestamps]}
_user_hits: dict[tuple[str, str], list[float]] = defaultdict(list)
_user_last_eviction: float = 0.0


def _prune_user(timestamps: list[float], now: float, window: int) -> list[float]:
    """Remove timestamps older than *window* seconds."""
    cutoff = now - window
    return [t for t in timestamps if t > cutoff]


def per_user_rate_limit(
    max_requests: int,
    window_seconds: int = WINDOW_SECONDS,
    scope: str = "default",
):
    """
    Factory that returns a FastAPI dependency enforcing a per-user
    sliding-window rate limit.

    Parameters
    ----------
    max_requests : int
        Maximum number of requests allowed within *window_seconds*.
    window_seconds : int
        Length of the sliding window in seconds (default: 60).
    scope : str
        Namespace to separate counters for different endpoint groups
        (e.g. ``"intake"`` vs ``"vision"``).

    Usage::

        intake_limit = per_user_rate_limit(30, scope="intake")

        @router.post("/process")
        async def process(
            ...,
            _rl: None = Depends(intake_limit),
        ):
            ...
    """

    async def _check(
        user_id: str = Depends(get_current_user_id),
    ) -> None:
        if not PER_USER_RATE_LIMIT_ENABLED:
            return

        key = (scope, user_id)
        now = time.monotonic()

        _user_hits[key] = _prune_user(_user_hits[key], now, window_seconds)

        if len(_user_hits[key]) >= max_requests:
            # Calculate Retry-After: seconds until the oldest hit expires
            oldest = _user_hits[key][0]
            retry_after = max(1, math.ceil((oldest + window_seconds) - now))
            logger.warning(
                "Per-user rate limit exceeded: user=%s scope=%s (%d/%d in %ds)",
                user_id,
                scope,
                len(_user_hits[key]),
                max_requests,
                window_seconds,
            )
            from app.errors import error_response
            from app.lib.error_codes import ErrorCode
            raise error_response(
                429,
                "Per-user rate limit exceeded. Please try again later.",
                code=ErrorCode.RATE_LIMITED,
                headers={"Retry-After": str(retry_after)},
            )

        _user_hits[key].append(now)

        # Periodically evict empty keys to prevent unbounded memory growth
        global _user_last_eviction
        if now - _user_last_eviction > _EVICTION_INTERVAL:
            _user_last_eviction = now
            stale = [k for k, v in _user_hits.items() if not v]
            for k in stale:
                del _user_hits[k]
            if stale:
                logger.debug("Evicted %d stale user keys from rate limiter", len(stale))

    return _check
