"""
Worker registry for tracking worker health and scheduling.

Workers call `record_run()` when they complete a cycle.
The `/ops/worker-status` endpoint reads this registry.

Run history is persisted to the `worker_runs` DB table (survives restarts)
and also tracked in-memory for fast access.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Cooldown tracking for overdue alerts (epoch timestamp of last alert sent)
_last_overdue_alert_at: float = 0.0
_OVERDUE_ALERT_COOLDOWN_S: float = 3600.0  # 1 hour

# In-memory worker run tracking
# {worker_name: {"last_run": epoch, "last_status": "ok"|"error", "runs": int, "errors": int}}
_registry: dict[str, dict] = {}

# Default schedule intervals (seconds)
SCHEDULES = {
    "price_monitor": 6 * 3600,          # every 6 hours
    "vision_ingest": 0,                  # on-demand only
    "valuation_worker": 3 * 3600,        # every 3h (was 6h — raised drain rate
                                         # 2026-07-02 to catch up with the tcgcsv
                                         # bulk-import backlog; paired with
                                         # VALUATION_MAX_HITS_PER_CYCLE=25000)
    "deal_discovery": 1800,              # every 30 minutes
    "matview_demand": 600,               # every 10 minutes
    "matview_supply": 1800,              # every 30 minutes
    "task_worker": 5,                    # polls every 5 seconds
    "value_change_worker": 24 * 3600,    # daily
    "insights_digest_worker": 7 * 24 * 3600,  # weekly
    "watchlist_monitor_worker": 3600,    # every 1 hour
    "calibration_worker": 24 * 3600,     # daily
    "catalog_learning_worker": 1800,     # every 30 minutes
    "scarcity_monitor_worker": 6 * 3600, # every 6 hours
    "category_map_worker": 3600,         # every 1 hour
    "catalog_crawler_worker": 24 * 3600, # daily (nightly crawl)
    "model_retrain_worker": 7 * 24 * 3600,  # weekly
    "auto_delist_worker": 900,               # every 15 minutes
    "auction_alert_worker": 300,              # every 5 minutes
    "event_scraper_worker": 6 * 3600,       # every 6 hours
    "aggregate_catalog_attributes": 6 * 3600,  # R50k data flywheel — every 6h
    "feedback_loop_worker": 3600,                # every 1 hour — label_events → catalog
    "marketplace_scrape_worker": 900,            # every 15 min — actual cycles take 10-18 min due to per-adapter 30s timeouts; 5 min interval was firing "overdue" alerts on every run
    "tcgcsv_worker": 24 * 3600,                  # daily — TCGPlayer public price dump (MTG/Pokemon/Yugioh/Lorcana/OPTCG/Digimon)
    "discogs_worker": 24 * 3600,                 # daily — Discogs lowest asking-price for vinyl/anime_ost/city_pop
    "sanity_probe_worker": 3600,                 # R50l — hourly correctness checks on critical tables
    "discovery_audit_worker": 24 * 3600,         # R50l — daily broad discovery audit (orphan FKs, null rates, flow-through)
    "datalake_export_worker": 24 * 3600,         # R50m — nightly export of closed partitions → S3 parquet
    "partition_drop_worker": 24 * 3600,          # 2026-04-24 — daily detach+drop of >6mo partitions confirmed in S3 manifest
    "ticketmaster_events_worker": 12 * 3600,     # 2026-04-21 — Ticketmaster Discovery API → events (twice daily)
    "seatgeek_events_worker": 12 * 3600,         # 2026-04-21 — SeatGeek Search API → events (twice daily)
    "search_gap_worker": 6 * 3600,               # 2026-04-25 — turns 0-result searches into category_candidates
    "demand_priority_worker": 1800,              # 2026-04-25 — refreshes top-N items by recent demand_signals (every 30 min)
    "vision_quality_worker": 6 * 3600,           # 2026-04-25 — recomputes vision_category_quality from scan_corrections (6h; was hourly but no data → no signal until users accrue scan_corrections)
    "vision_reclassifier_worker": 7 * 24 * 3600, # 2026-04-25 — trains TF-IDF + LogReg text reclassifier on scan_corrections (weekly; gated on n>=1000)
    "vision_regret_worker": 6 * 3600,            # 2026-04-26 — per-category regret rate (deletes within 7d of AI-add); was hourly, dropped to 6h until items.source signals accrue
    "event_engagement_worker": 1800,             # 2026-04-26 — recomputes events.engagement_score from views+follows+RSVPs+ticket_clicks (every 30 min)
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
    # Skip overdue checks for matview workers — non-critical refresh jobs
    # that frequently miss cycles during scraping. Not worth alerting on.
    if "matview" in worker_name:
        return False

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
        if "matview" in name:
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


def record_run(
    worker_name: str,
    status: str = "ok",
    duration_s: Optional[float] = None,
    error_repr: Optional[str] = None,
) -> None:
    """Record a worker run completion (in-memory + best-effort DB persist).

    Args:
        worker_name: identifier for the worker
        status: "ok" or "error"
        duration_s: wall-clock seconds the run took (optional)
        error_repr: short exception summary (type + message + first frame),
                    persisted into worker_runs.metadata.error_repr so loud-
                    but-empty errors don't hide their cause. Added 2026-04-22
                    after the auction_alert / auto_delist / watchlist_monitor
                    33%-error pattern surfaced with empty metadata.
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
        _persist_run_to_db(worker_name, status, error_repr=error_repr)
    except Exception:
        logger.debug("[worker_registry] Failed to trigger DB persist for %s", worker_name)


# Track fire-and-forget persist tasks so the GC doesn't drop them mid-flight
# (learning 2026-04-20: create_task without holding a reference lets Python
# drop the task before the INSERT completes, silently losing worker_runs rows
# and breaking the health monitor, silent_writer probe, and overdue alerts).
_pending_persist_tasks: set = set()


def _persist_run_to_db(
    worker_name: str,
    status: str,
    error_repr: Optional[str] = None,
) -> None:
    """Persist worker run to DB table (best-effort, sync-safe)."""
    try:
        from app.lib.db_helpers import get_db_pool
        pool = get_db_pool()
        if pool is None:
            return

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_async_persist_run(pool, worker_name, status, error_repr))
            # Hold a reference so GC doesn't drop the task.
            _pending_persist_tasks.add(task)

            def _on_done(t: asyncio.Task, wn: str = worker_name) -> None:
                _pending_persist_tasks.discard(t)
                exc = t.exception() if not t.cancelled() else None
                if exc is not None:
                    # Promote from debug → warning — without this, DB outages,
                    # connection-pool exhaustion, or schema drift can wipe out
                    # ALL worker_runs tracking in silence.
                    logger.warning(
                        "[worker_registry] persist task failed for %s: %r",
                        wn, exc,
                    )

            task.add_done_callback(_on_done)
        except RuntimeError:
            # No event loop running — skip DB persist
            logger.debug("[worker_registry] No event loop for DB persist of %s", worker_name)
    except Exception as e:
        logger.warning("[worker_registry] DB persist setup failed for %s: %r", worker_name, e)


async def _async_persist_run(
    pool,
    worker_name: str,
    status: str,
    error_repr: Optional[str] = None,
) -> None:
    """Async insert into worker_runs table. Re-raises on failure so the
    done-callback in _persist_run_to_db surfaces the error at WARNING.

    When error_repr is provided, writes it into metadata.error_repr so the
    cause of a 'loud-but-empty' error stays visible in worker_runs.
    """
    async with pool.acquire() as conn:
        if error_repr:
            await conn.execute(
                """
                INSERT INTO public.worker_runs (worker_name, status, metadata)
                VALUES ($1, $2, jsonb_build_object('error_repr', $3::text))
                """,
                worker_name,
                status,
                error_repr,
            )
        else:
            await conn.execute(
                """
                INSERT INTO public.worker_runs (worker_name, status)
                VALUES ($1, $2)
                """,
                worker_name,
                status,
            )


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


async def health_monitor_loop(interval_s: float = 900.0) -> None:
    """Background loop that calls check_and_alert_overdue() every *interval_s* seconds.

    Never raises — all exceptions are caught and logged so the task cannot crash.
    """
    logger.info("[health_monitor] Started (interval=%ds)", interval_s)
    while True:
        try:
            await asyncio.sleep(interval_s)
            await check_and_alert_overdue()
        except asyncio.CancelledError:
            logger.info("[health_monitor] Cancelled, exiting")
            return
        except Exception:
            logger.exception("[health_monitor] Unexpected error (will retry next cycle)")


async def check_and_alert_overdue(*, force: bool = False) -> bool:
    """Check for overdue workers and send a Telegram alert if any are found.

    Uses a 1-hour cooldown to avoid spamming.  Pass ``force=True`` to bypass
    the cooldown (useful for manual /ops endpoint calls).

    Returns True if an alert was sent, False otherwise.

    Workers that have *never* run are excluded — they would fire on every fresh
    restart and produce noise.  Only workers that ran at least once and then
    became overdue are reported.
    """
    global _last_overdue_alert_at

    now = time.time()
    if not force and (now - _last_overdue_alert_at) < _OVERDUE_ALERT_COOLDOWN_S:
        return False

    overdue = [
        w for w in get_overdue_workers()
        if w["last_run_ago_s"] is not None  # exclude never-ran workers
    ]
    if not overdue:
        return False

    # Build message
    lines: list[str] = ["\u26a0\ufe0f <b>Overdue Workers</b>\n"]
    for w in overdue:
        interval_min = round(w["expected_interval_s"] / 60, 1)
        ago_min = round(w["last_run_ago_s"] / 60, 1)
        status_tag = f' (last: {w["last_status"]})' if w["last_status"] else ""
        lines.append(
            f"\u2022 <b>{w['name']}</b> — last ran {ago_min}m ago "
            f"(expected every {interval_min}m){status_tag}"
        )

    lines.append(f"\n{len(overdue)} worker(s) overdue as of "
                  f"{datetime.now(timezone.utc).strftime('%H:%M UTC')}")

    try:
        from app.lib.telegram_ops import send_ops_alert

        sent = await send_ops_alert("\n".join(lines))
        if sent:
            _last_overdue_alert_at = now
            logger.info("[worker_registry] Overdue alert sent for %d worker(s)", len(overdue))
        return sent
    except Exception as exc:
        logger.warning("[worker_registry] Failed to send overdue alert: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Restart-proof cadence guard
# ---------------------------------------------------------------------------

async def seconds_since_last_ok(worker_name: str) -> Optional[float]:
    """Seconds since this worker's last `ok` run, from `worker_runs`.

    Returns None when there is no successful run on record, or when the DB is
    unavailable — callers must treat None as "no reason to skip".
    """
    try:
        from app.lib.db_helpers import get_db_pool
        pool = get_db_pool()
        if pool is None:
            return None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT EXTRACT(EPOCH FROM (now() - max(started_at)))::float AS age_s
                  FROM public.worker_runs
                 WHERE worker_name = $1 AND status = 'ok'
                """,
                worker_name,
            )
        return float(row["age_s"]) if row and row["age_s"] is not None else None
    except Exception as e:  # never let telemetry break a worker
        logger.debug("[worker_registry] seconds_since_last_ok(%s) failed: %s", worker_name, e)
        return None


async def should_skip_recent_run(worker_name: str, min_gap_s: float) -> bool:
    """True when this worker ran successfully less than `min_gap_s` ago.

    `SCHEDULES` sets the sleep BETWEEN cycles, but `_run_worker_loop` runs a
    worker immediately on start and the interval lives only in memory. So every
    restart of collectai-bake re-triggers every worker regardless of when it
    last ran. With 9-12 restarts on a busy day, a worker scheduled `24 * 3600`
    actually ran 9-12 times.

    That is how tcgcsv_worker reached ~14k requests/day against tcgcsv.com and
    got the application blocked for overuse on 2026-07-29
    (see learning_third_party_rate_bans_and_schedule_drift). discogs_worker was
    on the same trajectory at ~19k/day.

    Any worker that calls a third-party host on a slow schedule should gate its
    own work on this, so the cadence is a property of the worker rather than of
    how often the process happens to restart.
    """
    age = await seconds_since_last_ok(worker_name)
    if age is None:
        return False
    if age < min_gap_s:
        logger.info(
            "[worker_registry] %s skipping — last ok run was %.1fh ago (min gap %.1fh)",
            worker_name, age / 3600.0, min_gap_s / 3600.0,
        )
        return True
    return False
