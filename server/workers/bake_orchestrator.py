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
    # ── Signal alerts: DISABLED 2026-04-21. v_item_signal returned 0 rows
    # below the €15 threshold (catalog skews higher), and the INSERT path
    # references public.users which doesn't exist in Supabase (users live
    # in auth.users / profiles). Worker reported `ok` every cycle while
    # writing 0 alerts — classic silent-writer pattern. Re-enable only
    # after rewriting the threshold logic (e.g. %-drop vs prior q50) and
    # pointing the INSERT at the correct user table. Also commented out
    # of app/lib/worker_output_registry.py so sanity_probe stops paging.
    # ("signal_alerts_worker",    "workers.signal_alerts_worker",       "run_once", True),
    # ── Auction end-time alerts ──
    ("auction_alert_worker",    "workers.auction_alert_worker",       "run_once", True),
    # ── Aggregate catalog attributes (data flywheel) ──
    ("aggregate_catalog_attributes", "workers.aggregate_catalog_attributes", "run_once", False),
    # ── Feedback loop (label_events → catalog) ──
    ("feedback_loop_worker",    "workers.feedback_loop_worker",       "run_once", True),
    # ── tcgcsv + discogs: REMOVED FROM MANIFEST 2026-04-19.
    # PostgREST ?on_conflict=provider,listing_id stopped working after
    # market_hits was partitioned (42P10 "no matching unique constraint" —
    # Postgres requires partition-key columns in unique indexes on partitioned
    # tables). Re-enable after writing a Supabase RPC `upsert_market_hit` that
    # does WHERE NOT EXISTS server-side. See DATA_SCALING_PLAN.md §10 +
    # learnings.md.
    # ("tcgcsv_worker",           "pipelines.import_tcgcsv",  "run_once", True),
    # ("discogs_worker",          "pipelines.import_discogs", "run_once", True),
    # ── R50l sanity probe: hourly correctness checks on critical tables ──
    ("sanity_probe_worker",     "workers.sanity_probe_worker",        "run_once", True),
    # ── R50l discovery audit: daily broad sweep for orphaned/stale/drift data ──
    ("discovery_audit_worker",  "workers.discovery_audit_worker",     "run_once", True),
    # ── R50m datalake export: nightly parquet export of closed market_hits partitions ──
    ("datalake_export_worker",  "workers.datalake_export_worker",     "run_once", True),
    # ── Ticketmaster Discovery API → events (2026-04-21, twice-daily) ──
    ("ticketmaster_events_worker", "pipelines.ticketmaster_events",    "run_once", False),
    # ── SeatGeek Search API → events (2026-04-21, twice-daily) ──
    ("seatgeek_events_worker",  "pipelines.seatgeek_events",          "run_once", False),

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
# Track which workers are mid-cycle so light workers can yield when heavy
# ones are doing full-table scans / partition reads. Added 2026-04-19 after
# R4 audit showed probe queries repeatedly timing out during concurrent
# valuation_worker runs.
_in_flight: set[str] = set()

# "Heavy" workers do long-running full-table reads or writes and monopolise
# DB CPU when active. Light workers (probes/audits) should skip cycles when
# any heavy worker is in flight — the next hourly probe still catches new
# violations without fighting for resources.
_HEAVY_WORKERS: frozenset[str] = frozenset({
    "valuation_worker",
    "aggregate_catalog_attributes",
    "model_retrain_worker",
    "catalog_crawler_worker",
})
_LIGHT_YIELDING_WORKERS: frozenset[str] = frozenset({
    "sanity_probe_worker",
    "discovery_audit_worker",
})
_worker_import_failures: dict[str, str] = {}
# Workers we've already paged Telegram for — avoids re-paging every health tick
_alerted_workers: set[str] = set()
ALERT_THRESHOLD = int(os.getenv("BAKE_ALERT_THRESHOLD", "3"))

# 2026-04-20: previously when a worker task died (silent return, cancelled
# parent, or any exit without import failure) the supervisor logged "NOT
# restarting" and left the worker permanently gone. sanity_probe_worker
# stopped firing for 9h this way — we only noticed because the user
# complained that "probes stopped". Fix: actually supervise — re-spawn
# dead tasks with exponential backoff, and page Telegram on each restart
# so we find out in minutes, not days.
_worker_restart_counts: dict[str, int] = {}
_worker_manifest_by_name: dict[str, tuple[str, str, int, bool]] = {}
_MAX_RESTART_BACKOFF_S = 300.0


async def _send_telegram_alert(message: str) -> None:
    """Send an ops alert via telegram_ops. Never raises."""
    try:
        from app.lib.telegram_ops import send_ops_alert
        await send_ops_alert(message)
    except Exception as e:
        logger.warning("[bake_orchestrator] Telegram alert failed: %s", e)
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
        _worker_import_failures[name] = f"{type(e).__name__}: {e}"
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
        # Light workers yield when heavy workers are mid-cycle — prevents
        # probes / audits from fighting valuation_worker for DB bandwidth.
        if name in _LIGHT_YIELDING_WORKERS:
            heavy_now = _in_flight & _HEAVY_WORKERS
            if heavy_now:
                logger.info(
                    "[bake_orchestrator] %s yielding this cycle — heavy workers in flight: %s",
                    name, sorted(heavy_now),
                )
                record_run(name, "ok", duration_s=0.0)  # not a failure, deferred
                try:
                    await asyncio.sleep(interval_s)
                    continue
                except asyncio.CancelledError:
                    return

        t0 = time.monotonic()
        _in_flight.add(name)
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
            # Capture exception type + message + the worker-frame in the
            # traceback so worker_runs.metadata.error_repr is populated
            # (was {} before 2026-04-22 — every loud error stayed opaque,
            # see learnings round 2 + 6/7).
            import traceback as _tb
            tb_frames = _tb.extract_tb(e.__traceback__)
            worker_frame = next(
                (f for f in reversed(tb_frames) if "/server/" in f.filename),
                tb_frames[-1] if tb_frames else None,
            )
            frame_str = (
                f" @ {worker_frame.filename.rsplit('/', 1)[-1]}:{worker_frame.lineno}"
                if worker_frame else ""
            )
            error_repr = f"{type(e).__name__}: {e!s}{frame_str}"[:500]
            try:
                record_run(name, "error", duration_s=duration, error_repr=error_repr)
            except Exception:
                pass
            logger.exception(
                "[bake_orchestrator] %s failed after %.1fs: %s", name, duration, e,
            )
        finally:
            _in_flight.discard(name)

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
                    if count >= ALERT_THRESHOLD and wname not in _alerted_workers:
                        _alerted_workers.add(wname)
                        await _send_telegram_alert(
                            f"⚠️ Bake worker {wname} has failed {count}× consecutively — "
                            f"check bake.log on collectai EC2."
                        )
                # Clear alert flag once a worker recovers
                for wname in list(_alerted_workers):
                    if wname not in _worker_errors:
                        _alerted_workers.discard(wname)

            if _worker_import_failures:
                for wname, err in sorted(_worker_import_failures.items()):
                    logger.error(
                        "[bake_orchestrator]   %s: IMPORT FAILED at startup (%s) — "
                        "deploy missing module and restart", wname, err,
                    )
                    alert_key = f"import:{wname}"
                    if alert_key not in _alerted_workers:
                        _alerted_workers.add(alert_key)
                        await _send_telegram_alert(
                            f"🔥 Bake worker {wname} FAILED TO IMPORT at startup "
                            f"({err}) — module likely not deployed to EC2."
                        )

            # Restart dead tasks (unless they were cancelled)
            for wname, task in list(_active_tasks.items()):
                if not task.done():
                    continue
                if task.cancelled():
                    continue
                exc = task.exception()
                import_err = _worker_import_failures.get(wname)
                if import_err:
                    logger.error(
                        "[bake_orchestrator] Task %s dead — import failure: %s",
                        wname, import_err,
                    )
                    continue
                manifest = _worker_manifest_by_name.get(wname)
                if manifest is None:
                    logger.warning(
                        "[bake_orchestrator] Task %s died (exc=%s) but no manifest entry "
                        "— cannot restart", wname, exc,
                    )
                    continue
                module_path, func_name, interval_s, needs_db_dsn = manifest
                count = _worker_restart_counts.get(wname, 0) + 1
                _worker_restart_counts[wname] = count
                backoff = min(_MAX_RESTART_BACKOFF_S, 5.0 * (2 ** min(count - 1, 6)))
                logger.warning(
                    "[bake_orchestrator] Task %s died (exc=%s) — respawning #%d after %.0fs",
                    wname, exc, count, backoff,
                )
                alert_key = f"restart:{wname}"
                if count >= ALERT_THRESHOLD and alert_key not in _alerted_workers:
                    _alerted_workers.add(alert_key)
                    await _send_telegram_alert(
                        f"⚠️ Bake worker {wname} respawned {count}× "
                        f"(last exc={exc}) — loop keeps exiting. Check bake.log."
                    )

                async def _respawn(n=wname, mp=module_path, fn=func_name,
                                   it=interval_s, nd=needs_db_dsn, bo=backoff):
                    await asyncio.sleep(bo)
                    await _run_worker_loop(n, mp, fn, it, nd)

                _active_tasks[wname] = asyncio.create_task(
                    _respawn(), name=f"orchestrator:{wname}",
                )

        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("[bake_orchestrator] Health summary error")


async def _instance_health_monitor(
    interval_s: float = 900.0,
    disk_threshold_pct: int = 80,
    rss_threshold_mb: int = 3000,
    # Tightened 2026-04-17 after a 16-min ingest dip went untriggered under
    # the old 60-min threshold. 30 min is the point where adapter outages
    # stop being transient and start meaning structural trouble.
    ingest_stale_minutes: int = 30,
    worker_runs_stale_minutes: int = 10,
) -> None:
    """Monitor EC2 instance health and alert on degradation.

    Alerts cover failure modes not tied to a single worker:
      * Disk fills up (R50j incident: 91% → logs/journals exploded)
      * RSS creeps toward the 4GB t3.medium limit (Crawl4AI + Chromium)
      * Ingest stalls (no market_hits for > threshold)
      * Worker loop stops recording (no worker_runs for > threshold)

    One alert per condition per occurrence; clears when healthy again.
    """
    import shutil
    import resource

    alerted: set[str] = set()
    # Delay first scan so ingest/workers have time to fire after startup.
    await asyncio.sleep(min(interval_s, 300.0))

    while True:
        try:
            issues: list[tuple[str, str]] = []

            # Disk
            try:
                total, used, _free = shutil.disk_usage("/")
                pct = (used / total) * 100
                if pct >= disk_threshold_pct:
                    issues.append((
                        "disk_full",
                        f"disk at {pct:.0f}% ({used/1e9:.1f}G / {total/1e9:.1f}G)",
                    ))
            except Exception as e:
                logger.debug("disk_usage probe failed: %s", e)

            # Memory (RSS of this process in MB on Linux; ru_maxrss is KB)
            try:
                rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss_mb = rss_kb / 1024
                if rss_mb >= rss_threshold_mb:
                    issues.append((
                        "memory_pressure",
                        f"RSS at {rss_mb:.0f}MB (limit {rss_threshold_mb}MB)",
                    ))
            except Exception as e:
                logger.debug("rusage probe failed: %s", e)

            # DB-side staleness probes
            dsn = os.getenv("DB_DSN")
            if dsn:
                try:
                    import asyncpg
                    conn = await asyncpg.connect(dsn, timeout=10)
                    try:
                        mh_recent = await conn.fetchval(
                            "SELECT count(*) FROM public.market_hits "
                            "WHERE seen_at > now() - ($1 || ' minutes')::interval",
                            str(ingest_stale_minutes),
                        )
                        if mh_recent == 0:
                            issues.append((
                                "ingest_stalled",
                                f"no market_hits inserted in last {ingest_stale_minutes}min",
                            ))
                        wr_recent = await conn.fetchval(
                            "SELECT count(*) FROM public.worker_runs "
                            "WHERE started_at > now() - ($1 || ' minutes')::interval",
                            str(worker_runs_stale_minutes),
                        )
                        if wr_recent == 0:
                            issues.append((
                                "worker_runs_stalled",
                                f"no worker_runs in last {worker_runs_stale_minutes}min — "
                                "orchestrator may be wedged",
                            ))
                        # Matview freshness: alert if a matview worker hasn't
                        # run in >6x its expected interval (scheduler wedged).
                        # matview_demand=600s (10m), matview_supply=1800s (30m).
                        for mv_name, stale_min in (("matview_demand", 60),
                                                   ("matview_supply", 180)):
                            mv_recent = await conn.fetchval(
                                "SELECT count(*) FROM public.worker_runs "
                                "WHERE worker_name = $1 AND started_at > "
                                "now() - ($2 || ' minutes')::interval",
                                mv_name, str(stale_min),
                            )
                            if mv_recent == 0:
                                issues.append((
                                    f"matview_stale_{mv_name}",
                                    f"{mv_name} has not refreshed in >{stale_min}min",
                                ))
                    finally:
                        await conn.close()
                except Exception as e:
                    logger.debug("DB staleness probe failed: %s", e)

            # Fire alerts for new issues, clear resolved ones
            current_keys = {k for k, _ in issues}
            for key, detail in issues:
                logger.warning("[bake_orchestrator] INSTANCE %s: %s", key, detail)
                if key not in alerted:
                    alerted.add(key)
                    await _send_telegram_alert(
                        f"🚨 Bake instance health: {key} — {detail}"
                    )
            for k in list(alerted):
                if k not in current_keys:
                    alerted.discard(k)
                    logger.info("[bake_orchestrator] INSTANCE %s cleared", k)
                    # Tell Telegram the issue resolved so an operator staring
                    # at the stale fire message knows it's over. Without this,
                    # every transient stall leaves a permanent-looking alert
                    # in the chat history. (2026-04-19: user reported seeing
                    # an ingest_stalled fire in Telegram 2h after ingest had
                    # already recovered.)
                    await _send_telegram_alert(
                        f"✅ Bake instance recovered: {k}"
                    )

        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("[bake_orchestrator] Instance health monitor error")

        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            return


async def _circuit_breaker_monitor(
    stale_open_threshold_s: float = 24 * 3600.0,
    interval_s: float = 3600.0,
) -> None:
    """Alert when adapter circuit breakers stay OPEN for > threshold.

    Stuck-open breakers mean the adapter is structurally dead (API closed,
    credentials revoked, upstream permanently down). Every retry cycle
    wastes CPU and fills the log with the same error. The operator should
    know so they can de-register the adapter.
    """
    alerted: set[str] = set()
    # Delay first scan so breakers have a chance to trip after startup.
    await asyncio.sleep(min(interval_s, 900.0))
    while True:
        try:
            from workers.circuit_breaker import all_circuit_status
            import time as _t

            statuses = all_circuit_status()
            now = _t.time()
            stuck = []
            for s in statuses:
                if s.get("state") != "open":
                    continue
                opened = s.get("open_since")
                if opened is None:
                    continue
                age = now - opened
                if age >= stale_open_threshold_s:
                    stuck.append((s["name"], age))

            if stuck:
                for name, age in stuck:
                    hours = age / 3600
                    logger.warning(
                        "[bake_orchestrator] Circuit '%s' OPEN for %.1fh — "
                        "likely structural failure", name, hours,
                    )
                    if name not in alerted:
                        alerted.add(name)
                        await _send_telegram_alert(
                            f"🔌 Adapter '{name}' circuit OPEN for {hours:.1f}h — "
                            f"structurally dead? Consider removing from scrape manifest."
                        )

            # Clear alerts for recovered breakers
            open_names = {s["name"] for s in statuses if s.get("state") == "open"}
            for n in list(alerted):
                if n not in open_names:
                    alerted.discard(n)

        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("[bake_orchestrator] Circuit-breaker monitor error")

        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            return


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

        _worker_manifest_by_name[registry_name] = (
            module_path, func_name, interval, needs_db_dsn,
        )
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
    asyncio.create_task(_circuit_breaker_monitor(), name="orchestrator:cb_monitor")
    asyncio.create_task(_instance_health_monitor(), name="orchestrator:instance_health")

    logger.info(
        "[bake_orchestrator] === STARTED %d workers, skipped %d ===",
        started, skipped,
    )
