"""
Metrics middleware for collectors backend.

Tracks request count and latency per endpoint using stdlib counters.
Exposes /metrics as a simple text endpoint compatible with Prometheus
text format (no prometheus_client dependency required).

main.py expects:
    from app.metrics import metrics_middleware, ensure_metrics_once
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable, Awaitable

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

logger = logging.getLogger(__name__)

_metrics_installed = False

# In-memory counters
_request_count: dict[str, int] = defaultdict(int)
_request_duration_sum: dict[str, float] = defaultdict(float)

EXEMPT_PATHS = frozenset({"/metrics", "/healthz", "/version", "/ops/status"})


def _label(method: str, path: str, status: int) -> str:
    """Create a metric label key."""
    # Normalize path to avoid cardinality explosion (strip IDs)
    parts = path.rstrip("/").split("/")
    normalized = "/".join(
        p if not _looks_like_id(p) else "{id}" for p in parts
    )
    return f'{method}|{normalized}|{status}'


def _looks_like_id(segment: str) -> bool:
    """Heuristic: UUIDs and long hex strings are IDs."""
    if len(segment) >= 20:
        return True
    # UUID format
    if len(segment) == 36 and segment.count("-") == 4:
        return True
    return False


async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Track request count and duration per endpoint."""
    path = request.url.path
    if path in EXEMPT_PATHS:
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start

    label = _label(request.method, path, response.status_code)
    _request_count[label] += 1
    _request_duration_sum[label] += duration

    return response


def _render_metrics() -> str:
    """Render metrics in Prometheus text exposition format."""
    lines = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
    ]
    for label, count in sorted(_request_count.items()):
        method, path, status = label.split("|", 2)
        lines.append(
            f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )

    lines.append("# HELP http_request_duration_seconds_sum Total request duration")
    lines.append("# TYPE http_request_duration_seconds_sum counter")
    for label, total in sorted(_request_duration_sum.items()):
        method, path, status = label.split("|", 2)
        lines.append(
            f'http_request_duration_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.4f}'
        )

    return "\n".join(lines) + "\n"


def ensure_metrics_once(app: FastAPI) -> None:
    """
    Idempotent hook to install the /metrics endpoint.
    """
    global _metrics_installed
    if _metrics_installed:
        return
    _metrics_installed = True

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return PlainTextResponse(_render_metrics(), media_type="text/plain")

    logger.info("Metrics endpoint installed at /metrics")
