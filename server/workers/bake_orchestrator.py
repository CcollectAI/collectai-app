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
import contextlib
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

# ── Pre-launch worker triage (2026-05-04) ───────────────────────────────
# Background: 2 weeks of patching the bake one worker at a time. Each fix
# was real but the rate of new fragility kept pace. App is pre-launch (no
# users), so most "live" workers are doing real work for nobody.
#
# Posture for pre-launch: keep ONLY the workers that produce data the
# App Store demo / launch readiness depends on. Disable the rest. Re-enable
# in waves post-launch as features ship.
#
# KEEP (10): valuation, marketplace_scrape, catalog_learning, calibration,
#   tcgcsv, discogs, category_map, feedback_loop, aggregate_catalog_attributes,
#   sanity_probe.
# DISABLE: everything else, with a per-worker reason inline.
#
# Combined with:
#   - single-slot semaphore on _HEAVY_WORKERS (cap concurrent DB pressure)
#   - bounded `statement_timeout` per worker (cap orphan-on-restart blast radius)
# ─────────────────────────────────────────────────────────────────────────
_WORKER_MANIFEST: list[tuple[str, str, str, bool]] = [
    # ── KEEP — pre-launch core ──
    # Predictions are the core product surface.
    ("valuation_worker",        "workers.valuation_worker",           "run_once", True),
    # Marketplace ingest feeds market_hits, which feeds predictions.
    ("marketplace_scrape_worker", "workers.marketplace_scrape_scheduler", "run_once", True),
    # Calibration measures prediction accuracy. Required for App Store demo.
    ("calibration_worker",      "workers.calibration_worker",         "run_once", True),
    # Catalog learning: vision-label → catalog mapping. Required for QuickScan flow.
    ("catalog_learning_worker", "workers.catalog_learning_worker",    "run_once", False),
    # Vision label → taxonomy mapper. Required for QuickScan flow.
    ("category_map_worker",     "workers.category_map_worker",        "run_once", True),
    # Feedback loop: scan corrections → catalog. Improves QuickScan accuracy.
    ("feedback_loop_worker",    "workers.feedback_loop_worker",       "run_once", True),
    # Catalog attribute aggregation — feeds FE attribute display.
    ("aggregate_catalog_attributes", "workers.aggregate_catalog_attributes", "run_once", False),
    # tcgcsv + discogs: bulk catalog growth. RE-ENABLED 2026-04-26 with
    # upsert_market_hits_batch RPC. Required for non-skewed catalog at launch.
    ("tcgcsv_worker",           "pipelines.import_tcgcsv",  "run_once", True),
    ("discogs_worker",          "pipelines.import_discogs", "run_once", True),
    # Sanity probe — must stay. Observability. If this is off, we're flying blind.
    ("sanity_probe_worker",     "workers.sanity_probe_worker",        "run_once", True),

    # ── DISABLED — post-launch features (no users yet) ──
    # ("catalog_crawler_worker",  "workers.catalog_crawler_worker",     "run_once", True),
    #   Nightly full crawl. Catalog imports (tcgcsv/discogs) cover pre-launch needs.
    # ("deal_discovery",          "workers.deal_discovery_worker",      "run_once", True),
    #   Paid-tier feature. No paid users.
    # ("price_monitor",           "workers.price_monitor_worker",       "run_once", True),
    #   Anomaly detection for user portfolios. No portfolios.
    # ("alerts_worker",           "workers.alerts_worker",              "run_once", True),
    #   User-facing low-value alerts. No users.
    # ("scarcity_monitor_worker", "workers.scarcity_monitor_worker",    "run_once", True),
    #   Scarcity feature for users. No users.
    # ("watchlist_monitor_worker", "workers.watchlist_monitor_worker",  "run_once", True),
    #   Watchlist alerts. 9 watchlist items in DB, all dev/seed.
    # ("auto_delist_worker",      "workers.auto_delist_worker",         "run_once", True),
    #   Cross-marketplace listing sync. No connected sellers.
    # ("event_scraper_worker",    "workers.event_scraper_scheduler",    "run_once", False),
    #   Events feature for users. No users.
    # ("value_change_worker",     "workers.value_change_worker",        "run_once", True),
    #   Daily portfolio notifications. No portfolios.
    # ("auction_alert_worker",    "workers.auction_alert_worker",       "run_once", True),
    #   Disabled 2026-05-04 due to partition-pruning planner regression
    #   (see learning_partition_pruning_planning_cost.md). Re-enable after
    #   query rewrite. Even before this incident: user-facing alerts, no users.
    # ("signal_alerts_worker",    "workers.signal_alerts_worker",       "run_once", True),
    #   Disabled 2026-04-21: silent-writer pattern + wrong table reference.
    # ("discovery_audit_worker",  "workers.discovery_audit_worker",     "run_once", True),
    #   Daily broad data sweep. Useful post-scale, not load-bearing pre-launch.
    # ("datalake_export_worker",  "workers.datalake_export_worker",     "run_once", True),
    #   Nightly parquet export to S3. Storage cost optimization, post-launch.
    # ("partition_drop_worker",   "workers.partition_drop_worker",      "run_once", True),
    #   Drops >6mo partitions. We don't have >6mo data yet.
    # ("ticketmaster_events_worker", "pipelines.ticketmaster_events",    "run_once", False),
    # ("seatgeek_events_worker",  "pipelines.seatgeek_events",          "run_once", False),
    #   Events ingest. Events feature gated post-launch.
    # ("offer_expiry_worker",     "workers.offer_expiry_worker",        "run_once", True),
    #   Deal Desk offers. No deals.
    # ("search_gap_worker",       "workers.search_gap_worker",          "run_once", True),
    #   Turns user 0-result searches into category candidates. No users searching.
    # ("demand_priority_worker",  "workers.demand_priority_worker",     "run_once", True),
    #   Refresh top-N items by demand_signals. No demand signals from users.
    # ("vision_quality_worker",   "workers.vision_quality_worker",      "run_once", True),
    # ("vision_reclassifier_worker", "workers.vision_reclassifier_worker", "run_once", True),
    # ("vision_regret_worker",    "workers.vision_regret_worker",       "run_once", True),
    #   Vision learning loop. Needs scan_corrections from real users to be useful.
    # ("event_engagement_worker", "workers.event_engagement_worker",    "run_once", True),
    #   events.engagement_score from views+RSVPs. No engagement.

    # ── Workers with their own scheduler_loop ──
    # matview_refresh — handled in start_all_workers() below.

    # ── Skipped / on-demand ──
    # vision_ingest — on-demand only (interval=0)
    # model_retrain_worker — handled by nightly GHA workflow
    # task_worker — polls every 5s, handled separately in main.py
]

# Weekly workers — disabled for pre-launch. Re-enable post-launch.
_WEEKLY_WORKERS: list[tuple[str, str, str, bool]] = [
    # ("insights_digest_worker", "workers.insights_digest_worker", "run_once", True),
    #   Weekly digest email. No users.
]


# ── Per-worker error tracking for health summary ─────────────────────────
_worker_errors: dict[str, int] = {}
_worker_last_ok: dict[str, float] = {}
# When the current error streak started (epoch s). Reset to None on any ok run.
# Used by `_health_summary_loop` to page on "erroring for >N minutes straight"
# in addition to the count-based ALERT_THRESHOLD. Catches slow-cycling workers
# (interval 1h+) that never hit the count threshold but are still degraded.
_worker_first_error_at: dict[str, float] = {}
# How long a worker can be in an error streak before it gets a sustained-error
# Telegram page. Independent of ALERT_THRESHOLD's count-based path.
SUSTAINED_ERROR_PAGE_AFTER_S = float(
    os.getenv("BAKE_SUSTAINED_ERROR_PAGE_AFTER_S", "1800")  # 30 min default
)
# Workers we've already sustained-error-paged this streak. Reset on first ok.
_sustained_error_alerted: set[str] = set()

# ── Supabase circuit breaker ─────────────────────────────────────────────
# Sliding-window counter of DB-side errors (statement_timeout, REST 503,
# Postgres 57014). When the rate crosses the degraded threshold, light
# workers skip cycles instead of piling onto an already-saturated pool.
# Heavy workers still run (gated by `_HEAVY_LOCK` to one at a time) — they
# represent real work the bake exists to do; lights can be deferred.
#
# 2026-05-04 incident: 14 workers stayed in error state for 30+ min
# because every retry slammed into the same saturated Supabase. The
# breaker turns those retries into yields, letting the DB recover.
import collections as _collections
_db_error_window: "_collections.deque[float]" = _collections.deque(maxlen=500)
DB_DEGRADED_THRESHOLD = int(os.getenv("BAKE_DB_DEGRADED_THRESHOLD", "5"))
DB_DEGRADED_WINDOW_S = float(os.getenv("BAKE_DB_DEGRADED_WINDOW_S", "300"))
_db_degraded_alerted = False


def _register_db_error(error_repr: str) -> bool:
    """Record a DB-level error if the error_repr looks DB-related.

    Returns True if the error was recorded (i.e., counts toward circuit-breaker).
    Idempotent: callers can pass any error_repr without filtering.
    """
    s = (error_repr or "").lower()
    if (
        "statement_timeout" in s
        or "canceling statement" in s
        or "57014" in s
        or "querycanceled" in s
        or "the read operation timed out" in s
        or "http 500" in s and "57014" in s  # belt-and-braces
    ):
        _db_error_window.append(time.time())
        return True
    return False


def _is_db_degraded() -> bool:
    """True if the DB-error rate is above the degraded threshold."""
    if len(_db_error_window) < DB_DEGRADED_THRESHOLD:
        return False
    cutoff = time.time() - DB_DEGRADED_WINDOW_S
    recent = sum(1 for t in _db_error_window if t > cutoff)
    return recent >= DB_DEGRADED_THRESHOLD
# Track which workers are mid-cycle so light workers can yield when heavy
# ones are doing full-table scans / partition reads. Added 2026-04-19 after
# R4 audit showed probe queries repeatedly timing out during concurrent
# valuation_worker runs.
_in_flight: set[str] = set()

# "Heavy" workers do long-running full-table reads or writes that
# monopolise Supabase pool capacity when active. Two separate mechanisms
# protect against this:
#   1. Light workers (probes/audits) skip cycles when any heavy worker is
#      mid-cycle (`_LIGHT_YIELDING_WORKERS` × `_in_flight` check below).
#   2. Heavy workers themselves take a single global `_HEAVY_LOCK` so only
#      ONE heavy worker can hit the DB at a time. Without this the bake
#      ran 3+ heavy queries concurrently on 2026-05-04, saturated the
#      pooler, and every other worker timed out at 30s. The lock caps the
#      worst-case concurrent DB pressure to one heavy + N lights.
_HEAVY_WORKERS: frozenset[str] = frozenset({
    "valuation_worker",
    "aggregate_catalog_attributes",
    "model_retrain_worker",
    "catalog_crawler_worker",
    # Added 2026-05-04: bulk Supabase REST RPC writes saturate the pooler
    # the same way the asyncpg-direct heavies do. Treat them as heavy too.
    "marketplace_scrape_worker",
    "tcgcsv_worker",
    "discogs_worker",
})
_LIGHT_YIELDING_WORKERS: frozenset[str] = frozenset({
    "sanity_probe_worker",
    "discovery_audit_worker",
})
# Single-slot semaphore for heavy workers. Initialized lazily on first
# acquire because asyncio.Lock() requires a running loop in Python 3.10+.
_HEAVY_LOCK: asyncio.Lock | None = None

# Who currently holds the heavy gate, and the monotonic time they acquired it.
# Read by _instance_health_monitor to tell apart a benign ingest pause (the
# producer, marketplace_scrape_worker, is simply queued behind a long heavy
# run like valuation_worker's ~2.7h cycle) from a genuine producer death.
# None when the gate is free. Same-process module global — the monitor loop
# and the gate run in the orchestrator process, so a direct read is safe.
_HEAVY_HOLDER: tuple[str, float] | None = None

# Longest a heavy worker may legitimately hold the gate before a stalled
# ingest is treated as a real problem rather than benign queueing. The
# worst observed valuation_worker run is ~2.75h (9896s); 3h gives headroom.
# Past this, the holder is assumed wedged and we page despite the gate.
_HEAVY_GATE_SANE_CAP_S: float = float(
    os.getenv("BAKE_HEAVY_GATE_SANE_CAP_S", str(3 * 3600))
)


def _get_heavy_lock() -> asyncio.Lock:
    """Lazily create the single-slot heavy-worker lock on first use."""
    global _HEAVY_LOCK
    if _HEAVY_LOCK is None:
        _HEAVY_LOCK = asyncio.Lock()
    return _HEAVY_LOCK


@contextlib.asynccontextmanager
async def _heavy_gate(name: str):
    """Single-slot gate: heavy workers acquire the global lock; lights pass through.

    Heavy workers serialize through `_HEAVY_LOCK` so at most ONE heavy
    worker hits Supabase at a time. Lights are unaffected.

    Logs a one-line wait warning if a heavy worker had to queue >1s — that's
    the signal that the gate is doing real work.
    """
    if name not in _HEAVY_WORKERS:
        yield
        return
    lock = _get_heavy_lock()
    wait_start = time.monotonic()
    async with lock:
        waited = time.monotonic() - wait_start
        if waited > 1.0:
            logger.info(
                "[bake_orchestrator] %s waited %.1fs for heavy gate",
                name, waited,
            )
        global _HEAVY_HOLDER
        _HEAVY_HOLDER = (name, time.monotonic())
        try:
            yield
        finally:
            _HEAVY_HOLDER = None
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


async def _supervised(
    coro_factory,
    name: str,
    *,
    initial_delay: float = 5.0,
    max_delay: float = 300.0,
    alert_first_n_restarts: int = 3,
) -> None:
    """Respawn-on-exit wrapper for monitor loops.

    The 2026-04-20 fix added supervision *for workers* (`_health_summary_loop`
    re-spawns dead worker tasks). The monitor loops themselves were left
    unsupervised. On 2026-05-03 17:48:05 the health summary loop went silent
    for 39+ hours — `sanity_probe_worker` got cancelled at 19:30:47 and was
    never respawned because nothing was watching the watcher.

    Loop behaviour:
      - If the inner coro returns normally (it's an infinite loop, so this
        is a bug — log + respawn).
      - If it raises Exception — log + respawn with exponential backoff.
      - If it raises CancelledError mid-flight while the orchestrator is
        still alive (current task not being torn down) — respawn.
      - If our parent task is being cancelled (orchestrator shutdown) —
        re-raise CancelledError to let shutdown proceed.
      - KeyboardInterrupt / SystemExit always propagate.

    Telegram-pages on the first N restarts (default 3) so a wedged monitor
    surfaces in minutes, not days.
    """
    delay = initial_delay
    restart_count = 0
    while True:
        restart_count += 1
        crashed_repr: str | None = None
        try:
            await coro_factory()
            crashed_repr = "returned cleanly (should be infinite)"
            logger.warning(
                "[supervisor] %s %s — respawning #%d after %.0fs",
                name, crashed_repr, restart_count, delay,
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except asyncio.CancelledError:
            current = asyncio.current_task()
            # asyncio.Task.cancelling() is 3.11+. If we're being torn down
            # by the orchestrator, propagate. Otherwise treat as a stray
            # mid-flight cancel and respawn.
            cancelling = (
                current.cancelling() if current is not None
                and hasattr(current, "cancelling") else 0
            )
            if cancelling > 0:
                raise
            crashed_repr = "cancelled mid-flight"
            logger.warning(
                "[supervisor] %s %s — respawning #%d after %.0fs",
                name, crashed_repr, restart_count, delay,
            )
        except BaseException as e:
            crashed_repr = f"{type(e).__name__}: {e!s}"[:200]
            logger.exception(
                "[supervisor] %s crashed (%s) — respawning #%d after %.0fs",
                name, crashed_repr, restart_count, delay,
            )

        if restart_count <= alert_first_n_restarts:
            try:
                await _send_telegram_alert(
                    f"🔧 Supervisor respawning <b>{name}</b> (#{restart_count}) — "
                    f"reason: {crashed_repr}. Check bake.log."
                )
            except Exception:
                pass

        # Backoff sleep — but if the supervisor itself is being cancelled
        # (orchestrator shutdown), let the cancel propagate. Without this
        # check the wrapper would swallow the shutdown cancel and return
        # cleanly, which is fine in production but breaks deterministic
        # cancel-propagation in tests.
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            cancelling = (
                current.cancelling() if current is not None
                and hasattr(current, "cancelling") else 0
            )
            if cancelling > 0:
                raise
            return
        delay = min(max_delay, delay * 2)


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
        # Circuit breaker: when Supabase is in a DB-degraded window, *all*
        # light (non-heavy) workers skip the cycle. Heavies still run (gated
        # by _HEAVY_LOCK to one at a time) because they represent the real
        # ingest work; lights pile on retries with nothing useful to do.
        # 2026-05-04: prevents the cascade where every worker hammers a
        # saturated pool, keeping it saturated forever.
        if name not in _HEAVY_WORKERS and _is_db_degraded():
            logger.info(
                "[bake_orchestrator] %s skipping cycle — circuit breaker (DB degraded)",
                name,
            )
            record_run(name, "ok", duration_s=0.0)
            try:
                await asyncio.sleep(interval_s)
                continue
            except asyncio.CancelledError:
                return

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

        # Gate heavy workers through a single-slot lock — caps concurrent
        # DB pressure to at most one heavy + N lights. Lights pass through
        # the gate as a no-op. Wait time happens BEFORE t0 so the recorded
        # duration measures actual work, not queue wait.
        async with _heavy_gate(name):
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
                _worker_first_error_at.pop(name, None)
                _sustained_error_alerted.discard(name)
                logger.info(
                    "[bake_orchestrator] %s completed in %.1fs", name, duration,
                )
            except asyncio.CancelledError:
                logger.info("[bake_orchestrator] %s cancelled", name)
                _in_flight.discard(name)
                return
            except Exception as e:
                duration = time.monotonic() - t0
                _worker_errors[name] = _worker_errors.get(name, 0) + 1
                # Mark when this error streak started — used by
                # _health_summary_loop to page on sustained errors regardless
                # of cycle count (catches slow-cycling workers that never
                # hit the count-based ALERT_THRESHOLD before someone notices).
                if name not in _worker_first_error_at:
                    _worker_first_error_at[name] = time.time()
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
                # Feed circuit breaker: DB-side errors (statement_timeout,
                # REST 57014) increment the breaker counter; if rate crosses
                # threshold, light workers will skip their next cycle.
                _register_db_error(error_repr)
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
    global _db_degraded_alerted
    while True:
        await asyncio.sleep(interval_s)
        try:
            alive = sum(1 for t in _active_tasks.values() if not t.done())
            dead = sum(1 for t in _active_tasks.values() if t.done())
            errored = len(_worker_errors)
            db_degraded = _is_db_degraded()

            logger.info(
                "[bake_orchestrator] HEALTH: %d/%d workers alive, %d dead, %d with recent errors, db_degraded=%s",
                alive, alive + dead, dead, errored, db_degraded,
            )

            # Page once on degradation transition, page once on recovery.
            if db_degraded and not _db_degraded_alerted:
                _db_degraded_alerted = True
                await _send_telegram_alert(
                    "🚨 Bake circuit breaker OPEN — Supabase rate of "
                    "statement_timeout / 57014 above threshold. Light workers "
                    "are skipping cycles until the DB recovers. Check bake.log."
                )
            elif not db_degraded and _db_degraded_alerted:
                _db_degraded_alerted = False
                await _send_telegram_alert(
                    "✅ Bake circuit breaker CLOSED — DB recovered, "
                    "lights resuming."
                )

            if _worker_errors:
                now_s = time.time()
                for wname, count in sorted(_worker_errors.items()):
                    streak_started = _worker_first_error_at.get(wname)
                    streak_age_s = (now_s - streak_started) if streak_started else 0.0
                    logger.warning(
                        "[bake_orchestrator]   %s: %d consecutive errors (streak %.0fs)",
                        wname, count, streak_age_s,
                    )
                    # Count-based threshold (fast-cycling workers).
                    if count >= ALERT_THRESHOLD and wname not in _alerted_workers:
                        _alerted_workers.add(wname)
                        await _send_telegram_alert(
                            f"⚠️ Bake worker {wname} has failed {count}× consecutively — "
                            f"check bake.log on collectai EC2."
                        )
                    # Duration-based threshold (slow-cycling workers): catches
                    # the case where a 1-6h interval worker is erroring every
                    # cycle but never hits count >= 3 before someone notices.
                    # Independent alert key so this doesn't conflict with the
                    # count-based one above.
                    sustained_key = f"sustained:{wname}"
                    if (
                        streak_age_s >= SUSTAINED_ERROR_PAGE_AFTER_S
                        and sustained_key not in _sustained_error_alerted
                    ):
                        _sustained_error_alerted.add(sustained_key)
                        await _send_telegram_alert(
                            f"⚠️ Bake worker {wname} has been erroring for "
                            f"{streak_age_s/60:.0f} min straight ({count} cycles) — "
                            f"sustained failure, structural cause likely."
                        )
                # Clear alert flag once a worker recovers
                for wname in list(_alerted_workers):
                    if wname not in _worker_errors:
                        _alerted_workers.discard(wname)
                for sk in list(_sustained_error_alerted):
                    wname = sk.removeprefix("sustained:")
                    if wname not in _worker_errors:
                        _sustained_error_alerted.discard(sk)

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
                            # Distinguish a benign pause from a real outage.
                            # The producer (marketplace_scrape_worker) is a
                            # heavy worker, so it queues behind _HEAVY_LOCK.
                            # When another heavy worker holds the gate (e.g.
                            # valuation_worker's periodic ~2.7h run), ingest
                            # legitimately idles and recovers on its own — that
                            # fired a daily false page. Only alert when the gate
                            # is FREE (genuine producer death) or has been held
                            # absurdly long (the heavy worker itself is wedged).
                            holder = _HEAVY_HOLDER
                            held_s = (
                                time.monotonic() - holder[1] if holder else 0.0
                            )
                            if holder is None or held_s > _HEAVY_GATE_SANE_CAP_S:
                                extra = (
                                    f" (heavy gate held by {holder[0]} for "
                                    f"{held_s/60:.0f}min — likely wedged)"
                                    if holder else ""
                                )
                                issues.append((
                                    "ingest_stalled",
                                    f"no market_hits inserted in last "
                                    f"{ingest_stale_minutes}min{extra}",
                                ))
                            else:
                                logger.info(
                                    "[bake_orchestrator] ingest idle "
                                    "%dmin but heavy gate held by %s for "
                                    "%.0fmin — benign, not paging",
                                    ingest_stale_minutes, holder[0],
                                    held_s / 60,
                                )
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

    # Monitor loops — wrapped in `_supervised` so a stray cancel or
    # uncaught exception inside the loop doesn't permanently disable the
    # supervisor (2026-05-03 incident: health summary went silent for 39h
    # and sanity_probe_worker was never respawned).
    asyncio.create_task(
        _supervised(_health_summary_loop, "health_summary"),
        name="orchestrator:health_summary",
    )
    asyncio.create_task(
        _supervised(_circuit_breaker_monitor, "circuit_breaker_monitor"),
        name="orchestrator:cb_monitor",
    )
    asyncio.create_task(
        _supervised(_instance_health_monitor, "instance_health_monitor"),
        name="orchestrator:instance_health",
    )

    logger.info(
        "[bake_orchestrator] === STARTED %d workers, skipped %d ===",
        started, skipped,
    )
