"""
Admin Worker Health & Demand Summary endpoints.

Provides:
  ``GET /admin/worker-health``   — runtime health of every registered worker
  ``GET /admin/demand-summary``  — catalog demand signals for the owner

Protected by the ``OPS_API_KEY`` environment variable — callers must send
the key in the ``X-Ops-Key`` header.  Returns 403 when the key is missing
or incorrect.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import get_pool
from app.worker_registry import get_worker_health

_log = logging.getLogger("collectai.admin_health")

router = APIRouter(tags=["Admin"])


def _check_ops_key(request: Request) -> JSONResponse | None:
    """Validate OPS_API_KEY from request header. Returns error JSONResponse or None."""
    ops_key = os.getenv("OPS_API_KEY", "")
    provided = request.headers.get("X-Ops-Key", "")

    if not ops_key:
        _log.error("OPS_API_KEY is not configured — admin endpoint locked out")
        return JSONResponse(
            status_code=403,
            content={"detail": "OPS_API_KEY not configured on server"},
        )

    if not provided or provided != ops_key:
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid or missing X-Ops-Key header"},
        )

    return None


@router.get("/admin/worker-health", summary="Worker health status")
async def worker_health(request: Request) -> JSONResponse:
    """Return health status for all registered workers.

    Each worker entry includes: name, last_run_at, last_status (ok/error),
    run_count, average_duration_s, status (ok/overdue/never_run/on_demand),
    and minutes_overdue.

    Requires ``X-Ops-Key`` header matching the ``OPS_API_KEY`` env var.
    """
    err = _check_ops_key(request)
    if err is not None:
        return err

    return JSONResponse(get_worker_health())


@router.get("/admin/demand-summary", summary="Catalog demand signals summary")
async def demand_summary(request: Request) -> JSONResponse:
    """Return a summary of catalog demand signals for the app owner.

    Includes:
    - pending_suggestions: count of unprocessed suggestions
    - new_categories_watching: count of category candidates in 'watching' status
    - top_requested_items: items requested by most unique users, not yet in catalog
    - top_requested_categories: category candidates sorted by unique users
    - daily_request_counts: suggestion submissions per day for last 7 days

    Requires ``X-Ops-Key`` header matching the ``OPS_API_KEY`` env var.
    """
    err = _check_ops_key(request)
    if err is not None:
        return err

    pool = get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database not available"},
        )

    try:
        # Pending suggestions count
        pending_count: int = await pool.fetchval(
            "SELECT count(*) FROM catalog_suggestions WHERE status = 'pending'"
        ) or 0

        # Watching category candidates count
        watching_count: int = await pool.fetchval(
            "SELECT count(*) FROM category_candidates WHERE status = 'watching'"
        ) or 0

        # Top requested items (by unique user count, still pending)
        top_items_rows = await pool.fetch(
            """
            SELECT lower(suggested_name) AS name,
                   suggested_category,
                   count(*) AS total_requests,
                   count(DISTINCT user_id) AS unique_users,
                   max(created_at) AS last_requested
            FROM catalog_suggestions
            WHERE status = 'pending'
            GROUP BY lower(suggested_name), suggested_category
            ORDER BY unique_users DESC, total_requests DESC
            LIMIT 20
            """
        )
        top_items: list[dict[str, Any]] = [
            {
                "name": r["name"],
                "suggested_category": r["suggested_category"],
                "total_requests": r["total_requests"],
                "unique_users": r["unique_users"],
                "last_requested": r["last_requested"].isoformat() if r["last_requested"] else None,
            }
            for r in top_items_rows
        ]

        # Top requested categories (from category_candidates)
        top_cats_rows = await pool.fetch(
            """
            SELECT proposed_name, proposed_slug, signal_count,
                   unique_users, status, first_seen, last_seen
            FROM category_candidates
            ORDER BY unique_users DESC, signal_count DESC
            LIMIT 20
            """
        )
        top_categories: list[dict[str, Any]] = [
            {
                "name": r["proposed_name"],
                "slug": r["proposed_slug"],
                "signal_count": r["signal_count"],
                "unique_users": r["unique_users"],
                "status": r["status"],
                "first_seen": r["first_seen"].isoformat() if r["first_seen"] else None,
                "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            }
            for r in top_cats_rows
        ]

        # Daily request counts for last 7 days
        daily_rows = await pool.fetch(
            """
            SELECT date_trunc('day', created_at)::date AS day,
                   count(*) AS requests,
                   count(DISTINCT user_id) AS unique_users
            FROM catalog_suggestions
            WHERE created_at >= now() - interval '7 days'
            GROUP BY date_trunc('day', created_at)::date
            ORDER BY day DESC
            """
        )
        daily_counts: list[dict[str, Any]] = [
            {
                "day": r["day"].isoformat() if r["day"] else None,
                "requests": r["requests"],
                "unique_users": r["unique_users"],
            }
            for r in daily_rows
        ]

        return JSONResponse({
            "pending_suggestions": pending_count,
            "new_categories_watching": watching_count,
            "top_requested_items": top_items,
            "top_requested_categories": top_categories,
            "daily_request_counts": daily_counts,
        })

    except Exception as exc:
        _log.error("[admin-demand-summary] Failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch demand summary"},
        )
