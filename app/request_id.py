"""
Request ID middleware.

Assigns a unique short UUID to each request and makes it available via
contextvars for structured logging. Also adds X-Request-ID to response headers.

Usage:
    from app.request_id import get_request_id
    request_id = get_request_id()  # returns current request's UUID or ""
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)

_user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id", default=""
)


def get_request_id() -> str:
    """Get the current request ID (empty string if not in a request context)."""
    return _request_id_var.get()


def get_user_id() -> str:
    """Get the current user ID (empty string if not resolved yet)."""
    return _user_id_var.get()


def set_user_id(user_id: str) -> None:
    """Set the current user ID in the request context."""
    _user_id_var.set(user_id)


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Assign a request ID and attach it to the response."""
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
    try:
        import sentry_sdk as _sentry_sdk
        _sentry_sdk.set_tag("request_id", rid)
    except ImportError:
        pass
    token = _request_id_var.set(rid)
    user_token = _user_id_var.set("")

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        _user_id_var.reset(user_token)
        _request_id_var.reset(token)
