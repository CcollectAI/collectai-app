"""
Admin Worker Health endpoint.

Provides ``GET /admin/worker-health`` returning the runtime health of every
registered worker (name, last_run_at, last_status, run_count, average_duration).

Protected by the ``OPS_API_KEY`` environment variable — callers must send
the key in the ``X-Ops-Key`` header.  Returns 403 when the key is missing
or incorrect.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.worker_registry import get_worker_health

_log = logging.getLogger("collectai.admin_health")

router = APIRouter(tags=["Admin"])


@router.get("/admin/worker-health", summary="Worker health status")
async def worker_health(request: Request) -> JSONResponse:
    """Return health status for all registered workers.

    Each worker entry includes: name, last_run_at, last_status (ok/error),
    run_count, average_duration_s, status (ok/overdue/never_run/on_demand),
    and minutes_overdue.

    Requires ``X-Ops-Key`` header matching the ``OPS_API_KEY`` env var.
    """
    ops_key = os.getenv("OPS_API_KEY", "")
    provided = request.headers.get("X-Ops-Key", "")

    if not ops_key:
        _log.error("OPS_API_KEY is not configured — /admin/worker-health locked out")
        return JSONResponse(
            status_code=403,
            content={"detail": "OPS_API_KEY not configured on server"},
        )

    if not provided or provided != ops_key:
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid or missing X-Ops-Key header"},
        )

    return JSONResponse(get_worker_health())
