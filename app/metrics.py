"""
Stub metrics module for collectors backend.

main.py expects:
    from app.metrics import metrics_middleware, ensure_metrics_once

This stub keeps the app bootable without real metrics backend.
You can replace it later with Prometheus or other instrumentation.
"""

from __future__ import annotations

import logging
from typing import Callable, Awaitable

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_metrics_installed = False


async def metrics_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Minimal HTTP middleware that just forwards the request.
    """
    # You could add timing/logging here later.
    response = await call_next(request)
    return response


def ensure_metrics_once(app: FastAPI) -> None:
    """
    Idempotent hook to 'install' metrics once.

    In this stub, we only log once and do nothing else.
    """
    global _metrics_installed
    if _metrics_installed:
        return
    _metrics_installed = True
    logger.info("metrics stub: ensure_metrics_once called (no real metrics wired)")
