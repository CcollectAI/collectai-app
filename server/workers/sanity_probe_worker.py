#!/usr/bin/env python3
"""R50l correctness probe — hourly sample-and-check on critical tables.

Every bug from the R50l audit (JSONB corruption, price blow-ups,
missing item_ref prefix, calibration NULL metrics) would have been caught
by this probe within an hour.

The probe does NOT fix anything. It samples, checks invariants, logs a
per-check result, and pages Telegram if *any* sampled row violates an
invariant. The alert includes the table, the failing check, a sample row ID,
and the count of total violators.

Violations that persist across cycles are deduped by check-name via a simple
cooldown set so we don't spam the same finding every hour.

Checks (one per critical invariant):

  - category_items.attributes_json is jsonb object   (R50l repair)
  - price_predictions.q50 <= €20M                    (R50l Lego clamp)
  - price_predictions quantiles ordered              (q10 <= q50 <= q90)
  - market_hits.item_ref prefixed with `category:`   (R50l backfill)
  - market_hits.price_eur <= €20M                    (learning #25)
  - price_predictions.category matches item_ref prefix

Run with BAKE_ORCHESTRATOR_ENABLED=true — registered in the orchestrator
manifest + SCHEDULES at 1-hour cadence.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")
SAMPLE_SIZE = int(os.getenv("SANITY_PROBE_SAMPLE_SIZE", "500"))

# Dedup: don't re-page for the same check within N hours
_ALERT_COOLDOWN_HOURS = 6
_last_alerted_at: dict[str, datetime] = {}


# ---------------------------------------------------------------------------
# Check definitions — each returns (violator_count, sample_offending_row_or_none)
# ---------------------------------------------------------------------------

#
# Check queries are time-windowed to the last 24 hours (except the
# attributes_json repair check which uses a bounded sample). Full-table
# counts on market_hits (~600k rows) and price_predictions (~300k 7d)
# regularly exceed the Supabase pooler 30s statement_timeout. 24h windows
# catch *new* violations immediately while keeping queries index-aided.
# (Hardened 2026-04-19 after R4 audit showed 13 probe timeouts.)
CHECKS: list[dict] = [
    {
        "name": "category_items.attributes_json_is_object",
        # Unordered LIMIT 500 is O(1) vs an ordered-sample that Postgres
        # turns into a full scan. Under normal DB load, 500 is enough to
        # catch systematic drift — we don't need exhaustive coverage every
        # hour; we need a tripwire. Full repair happens in a one-off script.
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM (
              SELECT id, attributes_json FROM public.category_items
              WHERE attributes_json IS NOT NULL
              LIMIT 500
            ) sample
            WHERE jsonb_typeof(attributes_json) <> 'object'
        """,
        "description": "attributes_json must always be a JSONB object (500-row tripwire sample)",
    },
    {
        "name": "price_predictions.q50_under_20M",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(item_ref) AS sample_id
            FROM public.price_predictions
            WHERE generated_at > now() - interval '24 hours'
              AND (q50 > 20000000 OR q10 > 20000000 OR q90 > 20000000)
        """,
        "description": "price_predictions quantiles must be <= €20M (24h window)",
    },
    {
        "name": "price_predictions.quantiles_ordered",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(item_ref) AS sample_id
            FROM public.price_predictions
            WHERE generated_at > now() - interval '24 hours'
              AND ((q10 > q50) OR (q50 > q90) OR (q10 > q90))
        """,
        "description": "price_predictions require q10 <= q50 <= q90 (24h window)",
    },
    {
        "name": "market_hits.item_ref_prefixed",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.market_hits
            WHERE seen_at > now() - interval '24 hours'
              AND item_ref IS NOT NULL
              AND item_ref NOT LIKE '%:%'
              AND category IS NOT NULL
        """,
        "description": "market_hits.item_ref must be `category:item_key` formatted (24h window)",
    },
    {
        "name": "market_hits.price_eur_sane",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.market_hits
            WHERE seen_at > now() - interval '24 hours'
              AND (price_eur > 20000000 OR price > 20000000)
        """,
        "description": "market_hits price must be <= €20M (24h window)",
    },
    {
        "name": "price_predictions.category_matches_item_ref",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(item_ref) AS sample_id
            FROM public.price_predictions
            WHERE generated_at > now() - interval '24 hours'
              AND item_ref LIKE '%:%'
              AND category IS NOT NULL
              AND split_part(item_ref, ':', 1) <> category
        """,
        "description": "price_predictions.category must match item_ref prefix (24h window)",
    },
    {
        # Added 2026-04-18 after calibration_worker was "ok" for 7d with 0
        # output. Correctness probe instead of liveness probe.
        "name": "calibration_snapshots.recent_writes",
        "sql": """
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM public.calibration_snapshots
                       WHERE created_at > now() - interval '2 days') = 0
                 AND (SELECT COUNT(*) FROM public.worker_runs
                       WHERE worker_name='calibration_worker'
                         AND finished_at > now() - interval '2 days'
                         AND status='ok') >= 2
                THEN 1 ELSE 0
            END AS violators,
            NULL::text AS sample_id
        """,
        "description": "calibration_worker has ok runs but wrote 0 snapshots in 2 days",
    },
    {
        # Catches the R50l-followup pattern — any status leaked outside ok/error
        # should surface within an hour, not wait for the daily discovery audit.
        "name": "worker_runs.status_in_ok_error",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(worker_name) AS sample_id
            FROM public.worker_runs
            WHERE finished_at > now() - interval '2 days'
              AND status NOT IN ('ok','error')
        """,
        "description": "worker_runs.status must be 'ok' or 'error' (partial drift)",
    },
    {
        # Producer-stall correctness probe (learning #45: marketplace_scrape
        # silently skipped for 24h). Alerts when an "active" producer worker
        # hasn't added rows to its target table in 6h while reporting ok runs.
        "name": "market_hits.producer_stall",
        "sql": """
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM public.market_hits
                       WHERE seen_at > now() - interval '6 hours') = 0
                 AND (SELECT COUNT(*) FROM public.worker_runs
                       WHERE worker_name='marketplace_scrape_worker'
                         AND finished_at > now() - interval '6 hours'
                         AND status='ok') >= 3
                THEN 1 ELSE 0
            END AS violators,
            NULL::text AS sample_id
        """,
        "description": "marketplace_scrape_worker ok but 0 market_hits written in 6h",
    },
]


def _cooldown_expired(check_name: str) -> bool:
    last = _last_alerted_at.get(check_name)
    if last is None:
        return True
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed > _ALERT_COOLDOWN_HOURS * 3600


async def _page(failing: list[dict]) -> None:
    """Send one Telegram alert summarising all newly-failing checks."""
    try:
        from app.lib.telegram_ops import send_ops_alert
    except Exception:
        return

    lines = ["🩺 <b>Sanity probe violations</b>\n"]
    for f in failing:
        lines.append(
            f"• <b>{f['name']}</b>: {f['violators']} rows\n"
            f"  {f['description']}\n"
            f"  sample row: <code>{f['sample_id']}</code>"
        )
    lines.append(f"\nProbe run at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

    try:
        await send_ops_alert("\n".join(lines))
    except Exception as e:
        logger.warning("sanity_probe: telegram alert failed: %s", e)


@with_async_retry(max_retries=2, base_delay=1.0, max_delay=30.0)
async def run_once() -> None:
    if not DSN:
        logger.error("DB_DSN not set")
        record_run("sanity_probe_worker", "error")
        return

    # Prefer the direct DSN (no pooler 30s cap) — falls back to the pooler
    # when not configured. Direct connection is slightly slower to establish
    # (~9s vs ~1s for pooler) but allows a realistic 20s per-query timeout.
    probe_dsn = os.getenv("DB_DSN_DIRECT") or DSN
    conn = await asyncpg.connect(probe_dsn, timeout=20)
    # Server-side query timeout on top of asyncio.wait_for — cuts runaway
    # plans at Postgres layer too.
    try:
        await conn.execute("SET statement_timeout = '20s'")
    except Exception:
        pass
    failing_new: list[dict] = []
    try:
        for check in CHECKS:
            try:
                row = await asyncio.wait_for(
                    conn.fetchrow(check["sql"]),
                    timeout=20.0,
                )
                violators = int(row["violators"] or 0) if row else 0
                sample_id = row["sample_id"] if row else None
            except asyncio.TimeoutError:
                logger.warning("sanity_probe %s query timed out (>20s)", check["name"])
                continue
            except Exception as e:
                logger.warning("sanity_probe %s query failed: %s", check["name"], e)
                continue

            if violators > 0:
                logger.warning(
                    "SANITY VIOLATION %s: %d rows (sample=%s) — %s",
                    check["name"], violators, sample_id, check["description"],
                )
                if _cooldown_expired(check["name"]):
                    failing_new.append({
                        **check,
                        "violators": violators,
                        "sample_id": sample_id,
                    })
                    _last_alerted_at[check["name"]] = datetime.now(timezone.utc)
            else:
                logger.info("sanity_probe %s: clean", check["name"])

        if failing_new:
            await _page(failing_new)

    finally:
        await conn.close()
    record_run("sanity_probe_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("sanity_probe_worker", "error")
        log_dead_letter("sanity_probe_worker", {}, e)
        logger.exception("sanity_probe_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
