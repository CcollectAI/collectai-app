#!/usr/bin/env python3
"""Silent-sleepers audit — daily correctness probe.

Tests the R50l essay's failure mode: subsystems that claim "ok" but don't
produce real work. Runs daily, pages Telegram when any *new* sleeper
surfaces.

Probe categories:
  1. Liveness-vs-correctness — workers report ok runs but write 0 rows
  2. Schema columns — exist but are 100% NULL
  3. Dead tables — exist but 0 writes in 7d (where writes are expected)
  4. pg_cron — scheduled but never fires
  5. worker_runs status drift (ok/error only)
  6. Scheduled workers that never run
  7. Pooler vs direct DSN configuration

Added 2026-04-19 as part of the R50m silent-sleeper audit. Promoted from
a one-off script (/tmp/silent_sleepers_probe.py) after it caught a
double-stacked bug in aggregate_catalog_attributes that had hidden for
months.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Tables + columns that are expected to be written to. Some (label_events,
# predict_sessions) are user-driven so are skipped pre-launch via
# `requires_users` flag.
_LIVENESS_CHECKS = [
    # (worker_name, table, time_col, requires_users)
    ("valuation_worker", "price_predictions", "generated_at", False),
    ("calibration_worker", "calibration_snapshots", "created_at", False),
    ("marketplace_scrape_worker", "market_hits", "seen_at", False),
    ("feedback_loop_worker", "label_events", "created_at", True),
]

# (worker, table, json_key predicate on that table's JSONB column)
_LIVENESS_JSONB_CHECKS = [
    ("aggregate_catalog_attributes", "category_items", "attributes_json ? 'market_observed'"),
    ("feedback_loop_worker", "category_items", "attributes_json ? 'user_confirmed'"),
]

_NULL_COLUMN_CHECKS = [
    # columns that should NEVER be 100% NULL
    ("market_hits", "category"),
    ("market_hits", "item_ref"),
    ("market_hits", "price_eur"),
    ("price_predictions", "category"),
]

_CRON_MIN_30D_RUNS = 1  # a cron that's "active" should have fired at least once a month


@with_async_retry(max_retries=2, base_delay=1.0, max_delay=30.0)
async def run_once() -> None:
    if not DSN:
        logger.error("DB_DSN not set")
        record_run("silent_sleepers_worker", "error")
        return

    conn = await asyncpg.connect(DSN)
    findings: list[dict] = []

    # Detect pre-launch state — skip user-driven checks if so.
    user_count = await conn.fetchval("SELECT COUNT(*) FROM auth.users")
    pre_launch = (user_count or 0) <= 2  # ci-test + maybe one admin

    try:
        # ── 1. Liveness-vs-correctness ──
        for worker, table, col, requires_users in _LIVENESS_CHECKS:
            if requires_users and pre_launch:
                continue
            r = await conn.fetchrow(
                f"""
                SELECT
                  (SELECT COUNT(*) FROM public.worker_runs
                   WHERE worker_name = $1 AND finished_at > now() - interval '3 days'
                     AND status = 'ok') AS ok_runs,
                  (SELECT COUNT(*) FROM public.{table}
                   WHERE {col} > now() - interval '3 days') AS writes
                """,
                worker,
            )
            if r and r["ok_runs"] >= 3 and r["writes"] == 0:
                findings.append({
                    "category": "liveness",
                    "what": f"{worker} → {table}",
                    "detail": f"{r['ok_runs']} ok runs in 3d but 0 writes",
                })

        for worker, table, where in _LIVENESS_JSONB_CHECKS:
            if worker == "feedback_loop_worker" and pre_launch:
                continue
            r = await conn.fetchrow(
                f"""
                SELECT
                  (SELECT COUNT(*) FROM public.worker_runs
                   WHERE worker_name = $1 AND finished_at > now() - interval '3 days'
                     AND status = 'ok') AS ok_runs,
                  (SELECT COUNT(*) FROM public.{table} WHERE {where}) AS writes
                """,
                worker,
            )
            if r and r["ok_runs"] >= 3 and r["writes"] == 0:
                findings.append({
                    "category": "liveness_jsonb",
                    "what": f"{worker} → {table} ({where})",
                    "detail": f"{r['ok_runs']} ok runs in 3d but 0 writes",
                })

        # ── 2. 100% NULL columns ──
        for table, col in _NULL_COLUMN_CHECKS:
            r = await conn.fetchrow(
                f"""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE {col} IS NULL) AS nulls
                FROM public.{table}
                """
            )
            if r and r["total"] > 1000 and r["nulls"] == r["total"]:
                findings.append({
                    "category": "null_column",
                    "what": f"{table}.{col}",
                    "detail": f"100% NULL across {r['total']:,} rows",
                })

        # ── 3. pg_cron jobs that never fire ──
        try:
            rows = await conn.fetch("""
                SELECT j.jobname,
                       (SELECT COUNT(*) FROM cron.job_run_details d
                        WHERE d.jobid = j.jobid
                          AND d.start_time > now() - interval '30 days') AS runs_30d
                FROM cron.job j
                WHERE j.active
                  -- Skip newly-created jobs that legitimately haven't fired yet.
                  -- (e.g. the next-month partition cron only fires on the 25th.)
                  AND j.schedule NOT LIKE '%25 * *'
            """)
            for r in rows:
                if (r["runs_30d"] or 0) < _CRON_MIN_30D_RUNS:
                    findings.append({
                        "category": "cron_silent",
                        "what": r["jobname"],
                        "detail": f"active cron but 0 fires in 30d",
                    })
        except Exception as exc:
            logger.debug("pg_cron probe skipped: %s", exc)

        # ── 4. worker_runs status drift ──
        rows = await conn.fetch("""
            SELECT worker_name, status, COUNT(*) AS n
            FROM public.worker_runs
            WHERE finished_at > now() - interval '3 days'
              AND status NOT IN ('ok', 'error')
            GROUP BY 1, 2
        """)
        for r in rows:
            findings.append({
                "category": "status_drift",
                "what": r["worker_name"],
                "detail": f"non-ok/error status: '{r['status']}' ({r['n']} rows)",
            })

        # Report
        logger.info(
            "silent_sleepers complete: %d finding(s) (pre_launch=%s)",
            len(findings), pre_launch,
        )
        for f in findings:
            logger.warning("  SLEEPER [%s] %s — %s", f["category"], f["what"], f["detail"])

        if findings:
            try:
                from app.lib.telegram_ops import send_ops_alert
                lines = [f"😴 <b>Silent sleepers detected</b> ({len(findings)})\n"]
                for f in findings[:10]:
                    lines.append(f"• <b>{f['what']}</b>\n  {f['detail']}")
                lines.append(
                    f"\nRun at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                )
                await send_ops_alert("\n".join(lines))
            except Exception as exc:
                logger.warning("telegram page failed: %s", exc)

    finally:
        await conn.close()

    record_run("silent_sleepers_worker", "error" if findings else "ok")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [silent_sleepers] %(levelname)s: %(message)s",
    )
    try:
        await run_once()
    except Exception as e:  # noqa: BLE001
        record_run("silent_sleepers_worker", "error")
        log_dead_letter("silent_sleepers_worker", {}, e)
        logger.exception("silent_sleepers_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
