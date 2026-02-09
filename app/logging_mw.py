"""
Request logging middleware.

Logs method, path, status code, and duration for every request.
Exempt paths (health checks) are not logged to reduce noise.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("collectai.access")

EXEMPT_PATHS = frozenset({"/healthz", "/version", "/ops/status"})


async def logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log method, path, status, and duration for each request."""
    path = request.url.path

    if path in EXEMPT_PATHS:
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000

    logger.info(
        "%s %s %d %.0fms",
        request.method,
        path,
        response.status_code,
        duration_ms,
    )

    return response
