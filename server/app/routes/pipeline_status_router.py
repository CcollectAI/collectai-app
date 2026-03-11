"""
Pipeline status endpoint — reports last ingest and training run timestamps.

Queries model_registry and category_items to determine when pipelines last ran.
Public endpoint (no auth) for monitoring dashboards.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter

from app.db import db_configured, get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.get("/status", summary="Get pipeline health status")
async def pipeline_status() -> dict:
    """
    Return pipeline health summary.

    Reports:
    - Last training run per category (from model_registry)
    - Last ingest run (from category_items updated_at)
    - Overall staleness assessment
    """
    if not db_configured():
        return {
            "status": "unknown",
            "message": "Database not configured",
            "training": [],
            "ingest": {},
        }

    try:
        async with get_conn() as conn:
            # Latest model per category from model_registry
            training_rows = await conn.fetch(
                """
                SELECT category, version, is_active, train_size, mae, created_at
                FROM public.model_registry
                WHERE is_active = true
                ORDER BY category
                """
            )

            # Latest ingest timestamps per category from category_items
            ingest_rows = await conn.fetch(
                """
                SELECT category,
                       COUNT(*) AS item_count,
                       MAX(updated_at) AS last_updated
                FROM public.category_items
                GROUP BY category
                ORDER BY category
                """
            )

            # Count total market_hits (price observations)
            market_hits_count = await conn.fetchval(
                "SELECT COUNT(*) FROM public.market_hits"
            ) or 0

            # Latest market_hit timestamp
            latest_hit = await conn.fetchval(
                "SELECT MAX(created_at) FROM public.market_hits"
            )

    except Exception as e:
        logger.error("[pipeline/status] DB query failed: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "training": [],
            "ingest": {},
        }

    now = datetime.now(timezone.utc)

    # Format training status
    training: List[Dict[str, Any]] = []
    for row in training_rows:
        created = row["created_at"]
        hours_ago = (now - created).total_seconds() / 3600 if created else None
        training.append({
            "category": row["category"],
            "version": row["version"],
            "train_size": row["train_size"],
            "mae": float(row["mae"]) if row["mae"] is not None else None,
            "trained_at": created.isoformat() if created else None,
            "hours_ago": round(hours_ago, 1) if hours_ago is not None else None,
        })

    # Format ingest status
    ingest: Dict[str, Any] = {}
    for row in ingest_rows:
        last_updated = row["last_updated"]
        hours_ago = (now - last_updated).total_seconds() / 3600 if last_updated else None
        ingest[row["category"]] = {
            "item_count": row["item_count"],
            "last_updated": last_updated.isoformat() if last_updated else None,
            "hours_ago": round(hours_ago, 1) if hours_ago is not None else None,
        }

    # Overall staleness assessment
    stale_categories = [
        t["category"] for t in training
        if t["hours_ago"] is not None and t["hours_ago"] > 48
    ]

    return {
        "status": "healthy" if not stale_categories else "stale",
        "stale_categories": stale_categories,
        "training": {
            "models_count": len(training),
            "models": training,
        },
        "ingest": {
            "categories_count": len(ingest),
            "categories": ingest,
        },
        "market_data": {
            "total_hits": market_hits_count,
            "latest_hit_at": latest_hit.isoformat() if latest_hit else None,
        },
        "checked_at": now.isoformat(),
    }
