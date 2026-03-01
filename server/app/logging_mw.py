"""
Request logging middleware.

Logs method, path, status code, duration, and request_id for every request.
In production (DEV_MODE=false), outputs JSON structured logs.
In development, outputs human-readable format.

Exempt paths (health checks) are not logged to reduce noise.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response

from app.config import DEV_MODE
from app.request_id import get_request_id, get_user_id

logger = logging.getLogger("collectai.access")

EXEMPT_PATHS = frozenset({"/healthz", "/version", "/ops/status"})


async def logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log method, path, status, duration, and request_id for each request."""
    # Only log the path — exclude query string to avoid leaking sensitive params
    path = request.url.path

    if path in EXEMPT_PATHS:
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000

    request_id = get_request_id()
    user_id = get_user_id()

    if DEV_MODE:
        user_tag = f" user={user_id}" if user_id else ""
        logger.info(
            "[%s%s] %s %s %d %.0fms",
            request_id,
            user_tag,
            request.method,
            path,
            response.status_code,
            duration_ms,
        )
    else:
        # Structured JSON log line for production log aggregators
        log_record: dict[str, object] = {
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 1),
        }
        if user_id:
            log_record["user_id"] = user_id
        logger.info(json.dumps(log_record))

    return response
