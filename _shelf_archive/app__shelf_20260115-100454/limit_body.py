from __future__ import annotations

from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response


async def limit_body_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Stub body-size limiting middleware. Currently a no-op.
    """
    response = await call_next(request)
    return response
