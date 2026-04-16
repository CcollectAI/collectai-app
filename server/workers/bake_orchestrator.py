"""
Bake Orchestrator — single entry point that runs ALL workers in-process.

Replaces ad-hoc asyncio.create_task() calls scattered across main.py's
lifespan.  Each worker runs on its configured schedule from
worker_registry.SCHEDULES, with try/except isolation so one crash cannot
kill another worker.

Feature flag: BAKE_ORCHESTRATOR_ENABLED (default "true").

Usage from main.py lifespan:
    from workers.bake_orchestrator import start_all_workers
    await start_all_workers()
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger("bake_orchestrator")

# ── Worker manifest ──────────────────────────────────────────────────────
# Each entry: (registry_name, module_path, function_name, needs_db_dsn)
#
# registry_name  — key in worker_registry.SCHEDULES
# module_path    — dotted import path
# function_name  — async callable inside that module (usually "run_once")
# needs_db_dsn   — if True, skip when DB_DSN is not set

_WORKER_MANIFEST: list[tuple[str, str, str, bool]] = [
    # ── Critical: valuation (market_hits → price_predictions) ──
    ("valuation_worker",        "workers.valuation_worker",           "run_once", True),
    # ── Marketplace scrape (catalog → market_hits) ──
    ("marketplace_scrape_worker", "workers.marketplace_scrape_scheduler", "run_once", True),
    # ── Catalog crawler (nightly full crawl) ──
    ("catalog_crawler_worker",  "workers.catalog_crawler_worker",     "run_once", True),
    # ── Deal discovery ──
    ("deal_discovery",          "workers.deal_discovery_worker",      "run_once", True),
    # ── Price monitor (anomaly detection + threshold alerts) ──
    ("price_monitor",           "workers.price_monitor_worker",       "run_once", True),
    # ── Alerts worker (low-value alerts) ──
    ("alerts_worker",           "workers.alerts_worker",              "run_once", True),
    # ── Calibration (prediction accuracy measurement) ──
    ("calibration_worker",      "workers.calibration_worker",         "run_once", True),
    # ── Catalog learning (suggestion aggregation + auto-mapping) ──
    ("catalog_learning_worker", "workers.catalog_learning_worker",    "run_once", False),
    # ── Scarcity monitor ──
    ("scarcity_monitor_worker", "workers.scarcity_monitor_worker",    "run_once", True),
    # ── Watchlist monitor ──
    ("watchlist_monitor_worker", "workers.watchlist_monitor_worker",  "run_once", True),
    # ── Auto-delist (cross-marketplace inventory sync) ──
    ("auto_delist_worker",      "workers.auto_delist_worker",         "run_once", True),
    # ── Event scraper ──
    ("event_scraper_worker",    "workers.event_scraper_scheduler",    "run_once", False),
    # ── Value change (daily portfolio notifications) ──
    ("value_change_worker",     "workers.value_change_worker",        "run_once", True),
    # ── Category map (vision label → taxonomy) ──
    ("category_map_worker",     "workers.category_map_worker",        "run_once", True),
    # ── Signal alerts ──
    ("signal_alerts_worker",    "workers.signal_alerts_worker",       "run_once", True),
    # ── Auction end-time alerts ──
    ("auction_alert_worker",    "workers.auction_alert_worker",       "run_once", True),
    # ── Aggregate catalog attributes (data flywheel) ──
    ("aggregate_catalog_attributes", "workers.aggregate_catalog_attributes", "run_once", False),
    # ── Feedback loop (label_events → catalog) ──
    ("feedback_loop_worker",    "workers.feedback_loop_worker",       "run_once", True),

    # ── Workers with their own scheduler_loop (matview has split intervals) ──
    # matview_refresh uses its own scheduler_loop with demand/supply split
    # so we delegate to it directly rather than calling run_once in a loop.

    # ── Skipped / on-demand workers ──
    # vision_ingest            — on-demand only (interval=0)
    # model_retrain_worker     — handled by nightly GHA workflow
    # insights_digest_worker   — weekly, interval=604800, very long; include below
    # task_worker              — polls every 5s, handled separately in main.py
]

# Weekly workers — included but gated by their long intervals
_WEEKLY_WORKERS: list[tuple[str, str, str, bool]] = [
    ("insights_digest_worker", "workers.insights_digest_worker", "run_once", True),
]


# ── Per-worker error tracking for health summary ─────────────────────────
_worker_errors: dict[str, int] = {}
_worker_last_ok: dict[str, float] = {}
_active_tasks: dict[str, asyncio.Task] = {}


async def _run_worker_loop(
    name: str,
    module_path: str,
    func_name: str,
    interval_s: int,
    needs_db_dsn: bool,
) -> None:
    """Run a single worker's run_once() in a loop with sleep(interval)."""
    from app.worker_registry import record_run

    # Check DB_DSN requirement
    if needs_db_dsn and not os.getenv("DB_DSN"):
        logger.warning(
            "[bake_orchestrator] Skipping %s — DB_DSN not set", name,
        )
        return

    # Import the module and get the callable
    try:
        mod = __import__(module_path, fromlist=[func_name])
        run_fn = getattr(mod, func_name)
    except Exception as e:
        logger.error(
            "[bake_orchestrator] Failed to import %s.%s: %s", module_path, func_name, e,
        )
        return

    logger.info(
        "[bake_orchestrator] Starting %s (interval=%ds, module=%s)",
        name, interval_s, module_path,
    )

    # Stagger start: sleep a fraction to avoid all workers hitting DB at once
    stagger = hash(name) % min(60, interval_s // 2 + 1)
    await asyncio.sleep(stagger)

    while True:
        t0 = time.monotonic()
        try:
            # Some run_once() functions accept keyword args — call with no args
            # since the orchestrator always uses the default signature.
            # Special case: aggregate_catalog_attributes.run_once(dry_run=True)
            if name == "aggregate_catalog_attributes":
                await run_fn(dry_run=False)
            else:
                await run_fn()

            duration = time.monotonic() - t0
            record_run(name, "ok", duration_s=duration)
            _worker_last_ok[name] = time.time()
            _worker_errors.pop(name, None)
            logger.info(
                "[bake_orchestrator] %s completed in %.1fs", name, duration,
            )
        except asyncio.CancelledError:
            logger.info("[bake_orchestrator] %s cancelled", name)
            return
        except Exception as e:
            duration = time.monotonic() - t0
            _worker_errors[name] = _worker_errors.get(name, 0) + 1
            try:
                record_run(name, "error", duration_s=duration)
            except Exception:
                pass
            logger.exception(
                "[bake_orchestrator] %s failed after %.1fs: %s", name, duration, e,
            )

        # Sleep until next cycle
        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            logger.info("[bake_orchestrator] %s sleep cancelled", name)
            return


async def _health_summary_loop(interval_s: float = 1800.0) -> None:
    """Log a health summary every 30 minutes."""
    while True:
        await asyncio.sleep(interval_s)
        try:
            alive = sum(1 for t in _active_tasks.values() if not t.done())
            dead = sum(1 for t in _active_tasks.values() if t.done())
            errored = len(_worker_errors)

            logger.info(
                "[bake_orchestrator] HEALTH: %d/%d workers alive, %d dead, %d with recent errors",
                alive, alive + dead, dead, errored,
            )

            if _worker_errors:
                for wname, count in sorted(_worker_errors.items()):
                    logger.warning(
                        "[bake_orchestrator]   %s: %d consecutive errors", wname, count,
                    )

            # Restart dead tasks (unless they were cancelled)
            for wname, task in list(_active_tasks.items()):
                if task.done() and not task.cancelled():
                    exc = task.exception() if not task.cancelled() else None
                    logger.warning(
                        "[bake_orchestrator] Task %s died (exc=%s), NOT restarting "
                        "(worker loop should be infinite — check logs)",
                        wname, exc,
                    )

        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("[bake_orchestrator] Health summary error")


async def start_all_workers() -> None:
    """Spawn all worker loops as asyncio tasks. Call once from app lifespan."""
    enabled = os.getenv("BAKE_ORCHESTRATOR_ENABLED", "true").lower()
    if enabled not in ("true", "1"):
        logger.info("[bake_orchestrator] Disabled via BAKE_ORCHESTRATOR_ENABLED=%s", enabled)
        return

    from app.worker_registry import SCHEDULES

    all_workers = _WORKER_MANIFEST + _WEEKLY_WORKERS
    started = 0
    skipped = 0

    for registry_name, module_path, func_name, needs_db_dsn in all_workers:
        interval = SCHEDULES.get(registry_name, 0)
        if interval <= 0:
            logger.info(
                "[bake_orchestrator] Skipping %s (interval=0 / on-demand)", registry_name,
            )
            skipped += 1
            continue

        task = asyncio.create_task(
            _run_worker_loop(registry_name, module_path, func_name, interval, needs_db_dsn),
            name=f"orchestrator:{registry_name}",
        )
        _active_tasks[registry_name] = task
        started += 1

    # Also start the matview_refresh worker via its own scheduler_loop
    # (it has split demand/supply intervals, not a simple run_once loop)
    if os.getenv("MATVIEW_REFRESH_ENABLED", "true").lower() in ("true", "1"):
        try:
            from workers.matview_refresh_worker import scheduler_loop as matview_loop
            task = asyncio.create_task(matview_loop(), name="orchestrator:matview_refresh")
            _active_tasks["matview_refresh"] = task
            started += 1
            logger.info(
                "[bake_orchestrator] Starting matview_refresh (own scheduler_loop)",
            )
        except Exception as e:
            logger.warning("[bake_orchestrator] Failed to start matview_refresh: %s", e)

    # Start the health monitor from worker_registry
    try:
        from app.worker_registry import health_monitor_loop
        asyncio.create_task(health_monitor_loop(), name="orchestrator:health_monitor")
        logger.info("[bake_orchestrator] Health monitor started")
    except Exception as e:
        logger.warning("[bake_orchestrator] Failed to start health monitor: %s", e)

    # Start the task_worker if enabled (5s poll, handled separately)
    task_worker_enabled = os.getenv("TASK_WORKER_ENABLED", "false").lower() in ("true", "1")
    if task_worker_enabled:
        try:
            from app.lib.task_worker import run_worker as task_worker_loop
            poll_interval = int(os.getenv("TASK_WORKER_POLL_INTERVAL", "5"))
            task = asyncio.create_task(
                task_worker_loop(poll_interval=poll_interval),
                name="orchestrator:task_worker",
            )
            _active_tasks["task_worker"] = task
            started += 1
            logger.info("[bake_orchestrator] Task worker started (poll=%ds)", poll_interval)
        except Exception as e:
            logger.warning("[bake_orchestrator] Failed to start task worker: %s", e)

    # Health summary loop
    asyncio.create_task(_health_summary_loop(), name="orchestrator:health_summary")

    logger.info(
        "[bake_orchestrator] === STARTED %d workers, skipped %d ===",
        started, skipped,
    )
