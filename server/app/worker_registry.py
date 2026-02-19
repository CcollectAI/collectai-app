"""
Worker registry for tracking worker health and scheduling.

Workers call `record_run()` when they complete a cycle.
The `/ops/worker-status` endpoint reads this registry.
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
    "price_monitor": 6 * 3600,    # every 6 hours
    "alerts_worker": 3600,         # every 1 hour
    "vision_ingest": 0,            # on-demand only
    "valuation_worker": 6 * 3600,  # every 6 hours
    "deal_discovery": 1800,        # every 30 minutes
    "matview_refresh": 3600,       # every 1 hour
}


def record_run(worker_name: str, status: str = "ok") -> None:
    """Record a worker run completion."""
    entry = _registry.setdefault(worker_name, {"runs": 0, "errors": 0})
    entry["last_run"] = time.time()
    entry["last_status"] = status
    entry["runs"] += 1
    if status != "ok":
        entry["errors"] += 1


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
