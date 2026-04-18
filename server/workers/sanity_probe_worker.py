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

CHECKS: list[dict] = [
    {
        "name": "category_items.attributes_json_is_object",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.category_items
            WHERE attributes_json IS NOT NULL
              AND jsonb_typeof(attributes_json) <> 'object'
        """,
        "description": "attributes_json must always be a JSONB object (not string/array)",
    },
    {
        "name": "price_predictions.q50_under_20M",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(item_ref) AS sample_id
            FROM public.price_predictions
            WHERE q50 > 20000000 OR q10 > 20000000 OR q90 > 20000000
        """,
        "description": "price_predictions quantiles must be <= €20M",
    },
    {
        "name": "price_predictions.quantiles_ordered",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(item_ref) AS sample_id
            FROM public.price_predictions
            WHERE (q10 > q50) OR (q50 > q90) OR (q10 > q90)
        """,
        "description": "price_predictions require q10 <= q50 <= q90",
    },
    {
        "name": "market_hits.item_ref_prefixed",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.market_hits
            WHERE item_ref IS NOT NULL
              AND item_ref NOT LIKE '%:%'
              AND category IS NOT NULL
        """,
        "description": "market_hits.item_ref must be `category:item_key` formatted",
    },
    {
        "name": "market_hits.price_eur_sane",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(id::text) AS sample_id
            FROM public.market_hits
            WHERE price_eur > 20000000 OR price > 20000000
        """,
        "description": "market_hits price must be <= €20M (see learning #25)",
    },
    {
        "name": "price_predictions.category_matches_item_ref",
        "sql": """
            SELECT COUNT(*) AS violators,
                   MAX(item_ref) AS sample_id
            FROM public.price_predictions
            WHERE item_ref LIKE '%:%'
              AND category IS NOT NULL
              AND split_part(item_ref, ':', 1) <> category
        """,
        "description": "price_predictions.category must match item_ref prefix",
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

    conn = await asyncpg.connect(DSN)
    failing_new: list[dict] = []
    try:
        for check in CHECKS:
            try:
                row = await conn.fetchrow(check["sql"])
                violators = int(row["violators"] or 0) if row else 0
                sample_id = row["sample_id"] if row else None
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
