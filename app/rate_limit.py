"""
Sliding-window rate limiting middleware.

Limits requests per IP using an in-memory counter with a configurable
window (default: 60 requests per minute).

Configure via environment variables:
    RATE_LIMIT_RPM=60        # requests per minute per IP
    RATE_LIMIT_ENABLED=true  # set to false to disable
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
WINDOW_SECONDS = 60

# Exempt paths that should never be rate-limited
EXEMPT_PATHS = frozenset({"/healthz", "/version", "/ops/status"})

# In-memory sliding window: {ip: [timestamp, ...]}
_hits: dict[str, list[float]] = defaultdict(list)


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
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )

    _hits[ip].append(now)
    response = await call_next(request)
    return response
