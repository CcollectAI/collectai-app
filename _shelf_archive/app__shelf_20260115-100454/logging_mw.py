from __future__ import annotations

from typing import Callable, Awaitable

from starlette.requests import Request
from starlette.responses import Response


async def logging_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Simple logging stub. In production you can add real logging here.
    """
    response = await call_next(request)
    return response
