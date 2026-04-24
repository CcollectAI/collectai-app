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
from app.lib.worker_output_registry import WORKER_OUTPUTS
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
        # Use %s partition placeholder — substituted with the current-month
        # partition name at query time (e.g. market_hits_y2026m04). Postgres
        # runtime partition pruning won't always kick in on `seen_at > now() -
        # interval 'X'` because `now()` is evaluated late; hitting the
        # partition directly is deterministic and ~100x faster.
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.{current_month_partition}
            WHERE seen_at > now() - interval '24 hours'
              AND item_ref IS NOT NULL
              AND item_ref NOT LIKE '%:%'
              AND category IS NOT NULL
        """,
        "description": "market_hits.item_ref must be `category:item_key` formatted (24h)",
        "partition_scoped": True,
    },
    {
        "name": "market_hits.price_eur_sane",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.{current_month_partition}
            WHERE seen_at > now() - interval '24 hours'
              AND (price_eur > 20000000 OR price > 20000000)
        """,
        "description": "market_hits price must be <= €20M (24h)",
        "partition_scoped": True,
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
    {
        # Round-6 addition: 0-ingest probe is too lenient. 2026-04-20 saw
        # eBay + Vinted circuits trip out while yahoo + crawl4ai kept writing,
        # dropping ingest from 3000+/h → 200/h for 6h with no alert. New
        # check trips when last 1h hits fall below 20% of the trailing 24h
        # average AND the worker has been recording ok runs — meaning the
        # worker's still trying but the adapters are degraded.
        "name": "market_hits.volume_drop_vs_24h_avg",
        "sql": """
            WITH recent AS (
                SELECT COUNT(*)::float AS n1h
                FROM public.market_hits
                WHERE seen_at > now() - interval '1 hour'
            ),
            baseline AS (
                SELECT COUNT(*)::float / 24.0 AS avg_per_hour
                FROM public.market_hits
                WHERE seen_at BETWEEN now() - interval '25 hours'
                                  AND now() - interval '1 hour'
            )
            SELECT CASE
                WHEN baseline.avg_per_hour >= 100
                 AND recent.n1h < baseline.avg_per_hour * 0.20
                 AND (SELECT COUNT(*) FROM public.worker_runs
                       WHERE worker_name = 'marketplace_scrape_worker'
                         AND status = 'ok'
                         AND finished_at > now() - interval '1 hour') >= 3
                THEN 1 ELSE 0
            END AS violators,
            NULL::text AS sample_id
            FROM recent, baseline
        """,
        "description": "marketplace ingest last 1h < 20% of 24h-trailing average (likely external adapter outage)",
    },
]


async def _load_cooldowns_from_db(conn) -> None:
    """Hydrate _last_alerted_at from the DB so process restarts don't
    re-page already-alerted violations within the cooldown window.

    Uses worker_runs rows written by the probe itself — the most recent
    'ok' run's metadata carries a `paged` map of check_name -> iso_ts.
    Best-effort: failure leaves the in-memory dict empty (re-alert risk
    for one cycle, still better than losing cooldown entirely on restart).
    """
    if _last_alerted_at:  # already hydrated this process
        return
    try:
        row = await conn.fetchrow(
            "SELECT metadata FROM public.worker_runs "
            "WHERE worker_name = 'sanity_probe_worker' "
            "  AND status = 'ok' AND metadata ? 'paged' "
            "ORDER BY finished_at DESC NULLS LAST LIMIT 1"
        )
        if row and row["metadata"]:
            md = row["metadata"]
            if isinstance(md, str):
                import json as _json
                md = _json.loads(md)
            paged = md.get("paged") or {}
            for check_name, iso_ts in paged.items():
                try:
                    _last_alerted_at[check_name] = datetime.fromisoformat(iso_ts)
                except Exception:
                    pass
    except Exception as e:
        logger.debug("sanity_probe: could not hydrate cooldowns: %s", e)


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

    # HTML-escape user-supplied fragments — descriptions sometimes contain
    # `>` / `<` (e.g. "stale >6h") and Telegram's HTML parser treats them
    # as malformed tags and rejects the entire message with 400. Silent
    # failure mode: violation is logged but never delivered.
    import html as _html

    lines = ["🩺 <b>Sanity probe violations</b>\n"]
    for f in failing:
        name = _html.escape(str(f.get("name", "")))
        desc = _html.escape(str(f.get("description", "")))
        sample = _html.escape(str(f.get("sample_id", "")))
        lines.append(
            f"• <b>{name}</b>: {f['violators']} rows\n"
            f"  {desc}\n"
            f"  sample row: <code>{sample}</code>"
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

    # Resolve current-month partition name for queries that use
    # {current_month_partition} — dramatic speedup vs parent-table scans.
    now = datetime.now(timezone.utc)
    current_month_partition = f"market_hits_y{now.year:04d}m{now.month:02d}"

    # Rehydrate cooldown state from DB on first run of this process so
    # restarts don't cause an alert storm.
    await _load_cooldowns_from_db(conn)

    failing_new: list[dict] = []
    try:
        for check in CHECKS:
            sql = check["sql"]
            if check.get("partition_scoped"):
                sql = sql.format(current_month_partition=current_month_partition)
            try:
                row = await asyncio.wait_for(
                    conn.fetchrow(sql),
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

        # Silent-writer probe — cross-check declared output freshness against
        # worker_runs liveness. Added 2026-04-20 after 4 workers were found
        # recording ok for 48h+ while their output tables stayed stale.
        await _check_silent_writers(conn, failing_new)

        # DB-size probe — page when total DB size crosses alert threshold.
        # Default 6400 MB = 80% of Supabase Pro's 8GB cap. Adjust via
        # SUPABASE_DB_SIZE_ALERT_MB env var. Added 2026-04-24 because
        # DATA_SCALING_PLAN.md §7 calls for partition-drop automation that
        # doesn't yet exist; we want a tripwire if runway gets short.
        await _check_db_size(conn, failing_new)

        if failing_new:
            await _page(failing_new)
            # Persist cooldowns so a restart doesn't reset them.
            await _persist_cooldowns(conn)

    finally:
        await conn.close()
    record_run("sanity_probe_worker", "ok")


async def _persist_cooldowns(conn) -> None:
    """Write the current _last_alerted_at dict to the most recent
    sanity_probe_worker row's metadata as `paged: {name: iso_ts}`. The
    next process that starts can rehydrate via _load_cooldowns_from_db
    and honour the cooldown across restarts.
    """
    try:
        import json as _json
        paged = {n: ts.isoformat() for n, ts in _last_alerted_at.items()}
        await conn.execute(
            "UPDATE public.worker_runs "
            "SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb "
            "WHERE id = (SELECT id FROM public.worker_runs "
            "            WHERE worker_name = 'sanity_probe_worker' "
            "            ORDER BY started_at DESC LIMIT 1)",
            _json.dumps({"paged": paged}),
        )
    except Exception as e:
        logger.debug("sanity_probe: could not persist cooldowns: %s", e)


async def _check_silent_writers(conn, failing_new: list[dict]) -> None:
    """For each worker in WORKER_OUTPUTS, page if it's had recent ok runs
    but its declared output is stale beyond max_staleness_hours.

    Appends any violations to failing_new (the caller's accumulator). Never
    raises — individual check failures are logged and skipped so one dead
    table can't suppress the rest.
    """
    for worker_name, out in WORKER_OUTPUTS.items():
        check_name = f"silent_writer.{worker_name}"

        # Input gate — if the worker has no input to process, its 0-output
        # is correct, not a silent failure. Skip the check to avoid pages
        # in low-traffic / dev environments. (2026-04-20: the probe fired
        # on 5 workers that had no users/mandates/items to act on; this
        # gate stops that noise.)
        if out.input_exists_sql:
            try:
                row = await asyncio.wait_for(
                    conn.fetchrow(out.input_exists_sql),
                    timeout=10.0,
                )
                input_cnt = int(row["cnt"] or 0) if row else 0
            except Exception as e:
                logger.warning("sanity_probe %s input-gate failed: %s", check_name, e)
                continue
            if input_cnt == 0:
                logger.info("sanity_probe %s: skipped (no input)", check_name)
                continue

        where = f"AND ({out.where_clause})" if out.where_clause else ""
        sql = f"""
            SELECT CASE
                WHEN (
                    SELECT COUNT(*) FROM public.worker_runs
                     WHERE worker_name = $1
                       AND status = 'ok'
                       AND finished_at > now() - interval '2 hours'
                ) >= 2
                AND COALESCE(
                    EXTRACT(EPOCH FROM now() - (
                        SELECT MAX({out.timestamp_column}) FROM public.{out.table}
                         WHERE {out.timestamp_column} IS NOT NULL {where}
                    )) / 3600.0,
                    99999.0
                ) > $2
                THEN 1 ELSE 0
            END AS violators,
            $1::text AS sample_id
        """
        try:
            row = await asyncio.wait_for(
                conn.fetchrow(sql, worker_name, float(out.max_staleness_hours)),
                timeout=20.0,
            )
            violators = int(row["violators"] or 0) if row else 0
        except asyncio.TimeoutError:
            logger.warning("sanity_probe %s query timed out", check_name)
            continue
        except Exception as e:
            logger.warning("sanity_probe %s query failed: %s", check_name, e)
            continue

        if violators > 0:
            desc = (
                f"{worker_name} has ok runs in last 2h but "
                f"{out.table}.{out.timestamp_column} is stale >"
                f"{out.max_staleness_hours}h"
            )
            logger.warning("SILENT WRITER %s: %s", check_name, desc)
            if _cooldown_expired(check_name):
                failing_new.append({
                    "name": check_name,
                    "description": desc,
                    "violators": 1,
                    "sample_id": worker_name,
                })
                _last_alerted_at[check_name] = datetime.now(timezone.utc)
        else:
            logger.info("sanity_probe %s: clean", check_name)


async def _check_db_size(conn, failing_new: list[dict]) -> None:
    """Page when total DB size exceeds SUPABASE_DB_SIZE_ALERT_MB (default
    6400 MB = 80% of Supabase Pro's 8GB cap). Tripwire for partition-drop
    automation being late (DATA_SCALING_PLAN.md §7 week-8 deliverable).
    """
    check_name = "db_size_near_cap"
    try:
        size_bytes = await asyncio.wait_for(
            conn.fetchval("SELECT pg_database_size(current_database())"),
            timeout=5.0,
        )
    except Exception as e:
        logger.warning("sanity_probe db_size: query failed: %s", e)
        return

    size_mb = int(size_bytes / 1024 / 1024)
    cap_mb = int(os.getenv("SUPABASE_DB_SIZE_ALERT_MB", "6400"))

    if size_mb > cap_mb:
        logger.warning(
            "SANITY VIOLATION %s: DB %d MB > threshold %d MB",
            check_name, size_mb, cap_mb,
        )
        if _cooldown_expired(check_name):
            failing_new.append({
                "name": check_name,
                "description": (
                    f"DB size {size_mb} MB exceeds {cap_mb} MB alert threshold. "
                    "Ship partition-drop worker or raise tier."
                ),
                "violators": size_mb,
                "sample_id": f"{size_mb}MB",
            })
            _last_alerted_at[check_name] = datetime.now(timezone.utc)
    else:
        logger.info("sanity_probe db_size: %d MB (< %d MB cap)", size_mb, cap_mb)


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("sanity_probe_worker", "error")
        log_dead_letter("sanity_probe_worker", {}, e)
        logger.exception("sanity_probe_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
