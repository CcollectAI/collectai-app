"""
Worker registry for tracking worker health and scheduling.

Workers call `record_run()` when they complete a cycle.
The `/ops/worker-status` endpoint reads this registry.

Run history is persisted to the `worker_runs` DB table (survives restarts)
and also tracked in-memory for fast access.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory worker run tracking
# {worker_name: {"last_run": epoch, "last_status": "ok"|"error", "runs": int, "errors": int}}
_registry: dict[str, dict] = {}

# Default schedule intervals (seconds)
SCHEDULES = {
    "price_monitor": 6 * 3600,          # every 6 hours
    "alerts_worker": 3600,               # every 1 hour
    "vision_ingest": 0,                  # on-demand only
    "valuation_worker": 6 * 3600,        # every 6 hours
    "deal_discovery": 1800,              # every 30 minutes
    "matview_demand": 300,               # every 5 minutes
    "matview_supply": 1800,              # every 30 minutes
    "task_worker": 5,                    # polls every 5 seconds
    "value_change_worker": 24 * 3600,    # daily
    "insights_digest_worker": 7 * 24 * 3600,  # weekly
    "watchlist_monitor_worker": 3600,    # every 1 hour
    "calibration_worker": 24 * 3600,     # daily
    "catalog_learning_worker": 1800,     # every 30 minutes
}


def record_run(worker_name: str, status: str = "ok") -> None:
    """Record a worker run completion (in-memory + best-effort DB persist)."""
    entry = _registry.setdefault(worker_name, {"runs": 0, "errors": 0})
    entry["last_run"] = time.time()
    entry["last_status"] = status
    entry["runs"] += 1
    if status != "ok":
        entry["errors"] += 1

    # Best-effort persist to DB (non-blocking)
    try:
        _persist_run_to_db(worker_name, status)
    except Exception:
        pass


def _persist_run_to_db(worker_name: str, status: str) -> None:
    """Persist worker run to DB table (best-effort, sync-safe)."""
    try:
        from app.lib.db_helpers import get_db_pool
        pool = get_db_pool()
        if pool is None:
            return

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # Schedule as fire-and-forget task
            loop.create_task(_async_persist_run(pool, worker_name, status))
        except RuntimeError:
            # No event loop running — skip DB persist
            pass
    except Exception:
        pass


async def _async_persist_run(pool, worker_name: str, status: str) -> None:
    """Async insert into worker_runs table."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.worker_runs (worker_name, status)
                VALUES ($1, $2)
                """,
                worker_name,
                status,
            )
    except Exception as e:
        logger.debug("[worker_registry] Failed to persist run: %s", e)


def get_status() -> dict:
    """Get status of all registered workers."""
    now = time.time()
    workers = {}
    for name, schedule_interval in SCHEDULES.items():
        entry = _registry.get(name, {})
        last_run = entry.get("last_run")

        overdue = False
        if schedule_interval > 0 and last_run:
            overdue = (now - last_run) > (schedule_interval * 1.5)

        workers[name] = {
            "last_run_ago_s": round(now - last_run, 1) if last_run else None,
            "last_status": entry.get("last_status"),
            "total_runs": entry.get("runs", 0),
            "total_errors": entry.get("errors", 0),
            "schedule_interval_s": schedule_interval if schedule_interval > 0 else None,
            "overdue": overdue,
        }
    return workers
