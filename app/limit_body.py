"""
Body size limiting middleware.

Rejects requests whose Content-Length exceeds a configurable maximum
(default: 10 MB). Returns 413 Payload Too Large.

Configure via environment variables:
    MAX_BODY_BYTES=10485760   # 10 MB default
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 MB

# Paths exempt from body size checks
EXEMPT_PATHS = frozenset({"/healthz", "/version"})


async def limit_body_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    Reject requests with Content-Length exceeding MAX_BODY_BYTES.

    Returns 413 Payload Too Large when exceeded.
    """
    path = request.url.path
    if path in EXEMPT_PATHS:
        return await call_next(request)

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            length = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header"},
            )

        if length > MAX_BODY_BYTES:
            logger.warning(
                "Body too large: %d bytes from %s on %s (limit: %d)",
                length,
                request.client.host if request.client else "unknown",
                path,
                MAX_BODY_BYTES,
            )
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum allowed: {MAX_BODY_BYTES} bytes."
                },
            )

    return await call_next(request)
