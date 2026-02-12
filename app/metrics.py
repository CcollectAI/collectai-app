"""
Metrics middleware for collectors backend.

Tracks request count and latency per endpoint using stdlib counters.
Exposes /metrics and /ops/telemetry as text endpoints compatible with
Prometheus text exposition format (no prometheus_client dependency required).

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
_start_time = time.monotonic()

# In-memory counters — HTTP
_request_count: dict[str, int] = defaultdict(int)
_request_duration_sum: dict[str, float] = defaultdict(float)

# In-memory counters — Collector-specific
_collectors_requests_total = 0
_collectors_request_latency_seconds = 0.0
_collectors_inference_requests_total = 0
_collectors_task_failures_total = 0
_collectors_task_retries_total = 0

EXEMPT_PATHS = frozenset({"/metrics", "/ops/telemetry", "/healthz", "/version", "/ops/status"})

# Paths that count as inference requests
_INFERENCE_PREFIXES = ("/predict", "/intake/", "/vision/", "/marketplace/")


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


def record_task_failure() -> None:
    """Increment the task failure counter (call from workers on failure)."""
    global _collectors_task_failures_total
    _collectors_task_failures_total += 1


def record_task_retry() -> None:
    """Increment the task retry counter (call from workers on retry)."""
    global _collectors_task_retries_total
    _collectors_task_retries_total += 1


async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Track request count and duration per endpoint."""
    global _collectors_requests_total, _collectors_request_latency_seconds
    global _collectors_inference_requests_total

    path = request.url.path
    if path in EXEMPT_PATHS:
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start

    label = _label(request.method, path, response.status_code)
    _request_count[label] += 1
    _request_duration_sum[label] += duration

    # Collector-level counters
    _collectors_requests_total += 1
    _collectors_request_latency_seconds += duration

    if any(path.startswith(p) for p in _INFERENCE_PREFIXES):
        _collectors_inference_requests_total += 1

    return response


def _render_metrics() -> str:
    """Render metrics in Prometheus text exposition format."""
    uptime = time.monotonic() - _start_time

    lines: list[str] = []

    # --- Collector-level metrics ---
    lines.append("# HELP collectors_uptime_seconds_total Seconds since process start")
    lines.append("# TYPE collectors_uptime_seconds_total counter")
    lines.append(f"collectors_uptime_seconds_total {uptime:.2f}")

    lines.append("# HELP collectors_requests_total Total API requests processed")
    lines.append("# TYPE collectors_requests_total counter")
    lines.append(f"collectors_requests_total {_collectors_requests_total}")

    lines.append("# HELP collectors_request_latency_seconds Total request latency")
    lines.append("# TYPE collectors_request_latency_seconds counter")
    lines.append(f"collectors_request_latency_seconds {_collectors_request_latency_seconds:.4f}")

    lines.append("# HELP collectors_inference_requests_total Total inference requests")
    lines.append("# TYPE collectors_inference_requests_total counter")
    lines.append(f"collectors_inference_requests_total {_collectors_inference_requests_total}")

    lines.append("# HELP collectors_task_failures_total Total task failures")
    lines.append("# TYPE collectors_task_failures_total counter")
    lines.append(f"collectors_task_failures_total {_collectors_task_failures_total}")

    lines.append("# HELP collectors_task_retries_total Total task retries")
    lines.append("# TYPE collectors_task_retries_total counter")
    lines.append(f"collectors_task_retries_total {_collectors_task_retries_total}")

    # --- Per-endpoint HTTP metrics ---
    lines.append("# HELP http_requests_total Total HTTP requests by endpoint")
    lines.append("# TYPE http_requests_total counter")
    for label, count in sorted(_request_count.items()):
        method, path, status = label.split("|", 2)
        lines.append(
            f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )

    lines.append("# HELP http_request_duration_seconds_sum Total request duration by endpoint")
    lines.append("# TYPE http_request_duration_seconds_sum counter")
    for label, total in sorted(_request_duration_sum.items()):
        method, path, status = label.split("|", 2)
        lines.append(
            f'http_request_duration_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.4f}'
        )

    return "\n".join(lines) + "\n"


def ensure_metrics_once(app: FastAPI) -> None:
    """
    Idempotent hook to install /metrics and /ops/telemetry endpoints.
    """
    global _metrics_installed
    if _metrics_installed:
        return
    _metrics_installed = True

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return PlainTextResponse(_render_metrics(), media_type="text/plain")

    @app.get("/ops/telemetry", include_in_schema=False)
    async def telemetry_endpoint():
        return PlainTextResponse(_render_metrics(), media_type="text/plain")

    logger.info("Metrics endpoints installed at /metrics and /ops/telemetry")
