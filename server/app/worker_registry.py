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
    "scarcity_monitor_worker": 6 * 3600, # every 6 hours
    "category_map_worker": 3600,         # every 1 hour
    "signal_alerts_worker": 1800,        # every 30 minutes
    "matview_refresh": 0,                # single-run mode
    "catalog_crawler_worker": 24 * 3600, # daily (nightly crawl)
    "model_retrain_worker": 7 * 24 * 3600,  # weekly
    "auto_delist_worker": 900,               # every 15 minutes
}


# Public alias — maps worker names to their expected run intervals in seconds.
# Workers with interval 0 are on-demand/single-run and excluded from overdue checks.
WORKER_INTERVALS: dict[str, int] = {
    k: v for k, v in SCHEDULES.items() if v > 0
}


def is_overdue(worker_name: str) -> bool:
    """Check if a worker hasn't run within 1.5x its expected interval.

    Returns False for unknown workers or on-demand (interval=0) workers.
    Workers that have never run are considered overdue if they have a schedule.
    """
    interval = SCHEDULES.get(worker_name, 0)
    if interval <= 0:
        return False

    entry = _registry.get(worker_name)
    if not entry or "last_run" not in entry:
        # Never ran — overdue if it has a schedule
        return True

    elapsed = time.time() - entry["last_run"]
    return elapsed > (interval * 1.5)


def get_overdue_workers() -> list[dict]:
    """Return all overdue workers with details.

    Each entry contains:
      - name: worker name
      - expected_interval_s: configured interval in seconds
      - last_run_ago_s: seconds since last run (or None if never ran)
      - last_status: "ok" | "error" | None
      - overdue_by_s: how many seconds past the 1.5x threshold
    """
    now = time.time()
    overdue: list[dict] = []

    for name, interval in SCHEDULES.items():
        if interval <= 0:
            continue

        entry = _registry.get(name, {})
        last_run = entry.get("last_run")
        threshold = interval * 1.5

        if last_run is None:
            # Never ran
            overdue.append({
                "name": name,
                "expected_interval_s": interval,
                "last_run_ago_s": None,
                "last_status": None,
                "overdue_by_s": None,  # unknown — never ran
            })
            continue

        elapsed = now - last_run
        if elapsed > threshold:
            overdue.append({
                "name": name,
                "expected_interval_s": interval,
                "last_run_ago_s": round(elapsed, 1),
                "last_status": entry.get("last_status"),
                "overdue_by_s": round(elapsed - threshold, 1),
            })

    return overdue


def record_run(worker_name: str, status: str = "ok", duration_s: Optional[float] = None) -> None:
    """Record a worker run completion (in-memory + best-effort DB persist).

    Args:
        worker_name: identifier for the worker
        status: "ok" or "error"
        duration_s: wall-clock seconds the run took (optional)
    """
    entry = _registry.setdefault(worker_name, {"runs": 0, "errors": 0, "total_duration_s": 0.0, "duration_count": 0})
    entry["last_run"] = time.time()
    entry["last_status"] = status
    entry["runs"] += 1
    if status != "ok":
        entry["errors"] += 1
    if duration_s is not None:
        entry.setdefault("total_duration_s", 0.0)
        entry.setdefault("duration_count", 0)
        entry["total_duration_s"] += duration_s
        entry["duration_count"] += 1

    # Best-effort persist to DB (non-blocking)
    try:
        _persist_run_to_db(worker_name, status)
    except Exception:
        logger.debug("[worker_registry] Failed to trigger DB persist for %s", worker_name)


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
            logger.debug("[worker_registry] No event loop for DB persist of %s", worker_name)
    except Exception:
        logger.debug("[worker_registry] DB persist setup failed for %s", worker_name)


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


def get_worker_health() -> dict:
    """Return comprehensive health report for all scheduled workers.

    Returns a dict with:
      - workers: list of per-worker health entries
      - summary: counts of ok / overdue / never_run workers
      - checked_at: ISO timestamp of the check

    Each worker entry contains:
      - name: worker name
      - last_run_at: ISO timestamp of last run (or null)
      - expected_interval_minutes: configured interval in minutes
      - status: "ok" | "overdue" | "never_run" | "on_demand"
      - last_status: "ok" | "error" | null
      - run_count: lifetime run count
      - total_errors: lifetime error count
      - average_duration_s: mean wall-clock seconds per run (or null)
      - minutes_overdue: minutes past the 1.5x threshold (0 if not overdue, null if never_run)
    """
    from datetime import datetime, timezone

    now = time.time()
    workers: list[dict] = []
    counts = {"ok": 0, "overdue": 0, "never_run": 0, "on_demand": 0}

    for name, interval in SCHEDULES.items():
        entry = _registry.get(name, {})
        last_run_epoch = entry.get("last_run")
        dur_count = entry.get("duration_count", 0)
        avg_dur = round(entry["total_duration_s"] / dur_count, 2) if dur_count > 0 else None

        if interval <= 0:
            # On-demand / single-run workers
            workers.append({
                "name": name,
                "last_run_at": (
                    datetime.fromtimestamp(last_run_epoch, tz=timezone.utc).isoformat()
                    if last_run_epoch else None
                ),
                "expected_interval_minutes": None,
                "status": "on_demand",
                "minutes_overdue": None,
                "last_status": entry.get("last_status"),
                "run_count": entry.get("runs", 0),
                "total_errors": entry.get("errors", 0),
                "average_duration_s": avg_dur,
            })
            counts["on_demand"] += 1
            continue

        interval_minutes = round(interval / 60, 1)
        threshold = interval * 1.5

        if last_run_epoch is None:
            status = "never_run"
            minutes_overdue = None
            counts["never_run"] += 1
        else:
            elapsed = now - last_run_epoch
            if elapsed > threshold:
                status = "overdue"
                minutes_overdue = round((elapsed - threshold) / 60, 1)
                counts["overdue"] += 1
            else:
                status = "ok"
                minutes_overdue = 0
                counts["ok"] += 1

        workers.append({
            "name": name,
            "last_run_at": (
                datetime.fromtimestamp(last_run_epoch, tz=timezone.utc).isoformat()
                if last_run_epoch else None
            ),
            "expected_interval_minutes": interval_minutes,
            "status": status,
            "minutes_overdue": minutes_overdue,
            "last_status": entry.get("last_status"),
            "run_count": entry.get("runs", 0),
            "total_errors": entry.get("errors", 0),
            "average_duration_s": avg_dur,
        })

    # Sort: overdue first, then never_run, then ok, then on_demand
    status_order = {"overdue": 0, "never_run": 1, "ok": 2, "on_demand": 3}
    workers.sort(key=lambda w: (status_order.get(w["status"], 9), w["name"]))

    return {
        "workers": workers,
        "summary": counts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


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
