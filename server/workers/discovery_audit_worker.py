#!/usr/bin/env python3
"""Daily discovery audit — runs the R50l sweep queries against prod.

Fires one Telegram alert summarising any check that returned >0 violators,
with per-check counts. Dedup per-check via cooldown so repeat findings don't
spam.

Runs alongside sanity_probe_worker (hourly, narrow invariants). This worker
runs DAILY and covers broader discovery queries (orphan FKs, NULL rates,
stale data, scraper starvation, flow-through coverage).

This exists because 5 days of silent-bug pain taught us that liveness
probes + CHECK constraints miss whole classes of data-quality issues.
The sweep is our weekly safety net — if anything here returns rows, it
is a potential bug to investigate. See learnings.md essay "Why We Keep
Hitting New Problems Daily".
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logger = logging.getLogger(__name__)
DSN = os.getenv("DB_DSN")

# Dedup: don't re-page a specific check within N hours
_ALERT_COOLDOWN_HOURS = 24
_last_alerted_at: dict[str, datetime] = {}

# Each check: (name, severity, query, description, threshold)
# - severity: "critical" pages immediately; "warning" only pages if violator_count > 0
#   and cooldown has expired
# - threshold: violator count above which to page (most are 0; some are larger to
#   tolerate low-level noise)
CHECKS: list[dict] = [
    # --- A. Referential integrity ---
    # All check queries are time-windowed where possible. Full-table scans on
    # market_hits (~600k rows) and price_predictions (~300k 7d) regularly
    # exceed the Supabase pooler 30s statement_timeout. Hardened 2026-04-19
    # after R4 audit showed 13 probe timeouts.
    {
        "name": "orphan_predictions",
        "severity": "warning",
        "threshold": 2000,  # TCG cards (mtg/pokemon/yugioh) have long-tail sets not yet in curated catalog — tolerate signal without catalog entries
        "description": "price_predictions with item_ref not in category_items (7d window, excl. tcgplayer:* keys + mtg/pokemon/yugioh)",
        "sql": """
            SELECT COUNT(*) AS violators FROM public.price_predictions pp
            WHERE pp.generated_at > now() - interval '7 days'
              AND pp.item_ref IS NOT NULL AND pp.item_ref LIKE '%:%'
              AND pp.item_ref NOT LIKE '%:tcgplayer:%'
              AND split_part(pp.item_ref, ':', 1) NOT IN ('mtg','pokemon','yugioh')
              AND NOT EXISTS (
                SELECT 1 FROM public.category_items ci
                WHERE ci.category = split_part(pp.item_ref, ':', 1)
                  AND ci.item_key = substring(pp.item_ref FROM position(':' IN pp.item_ref) + 1)
              )
        """,
    },
    {
        "name": "orphan_market_hits",
        "severity": "warning",
        "threshold": 100000,  # tcgplayer/cardmarket/scryfall/ebay carry legit market signal for non-curated items; tolerate and alert only on regressions
        "description": "market_hits with item_ref not in category_items (7d window, excl. tcgcsv + mtg/pokemon/yugioh long-tail)",
        "sql": """
            SELECT COUNT(*) AS violators FROM public.market_hits mh
            WHERE mh.seen_at > now() - interval '7 days'
              AND mh.item_ref IS NOT NULL AND mh.item_ref LIKE '%:%'
              AND mh.provider <> 'tcgcsv'
              AND split_part(mh.item_ref, ':', 1) NOT IN ('mtg','pokemon','yugioh')
              AND NOT EXISTS (
                SELECT 1 FROM public.category_items ci
                WHERE ci.category = split_part(mh.item_ref, ':', 1)
                  AND ci.item_key = substring(mh.item_ref FROM position(':' IN mh.item_ref) + 1)
              )
        """,
    },
    # --- B. Freshness / temporal ---
    {
        "name": "future_timestamps",
        "severity": "critical",
        "threshold": 0,
        "description": "market_hits.seen_at is in the future (clock skew or bad parse)",
        "sql": "SELECT COUNT(*) AS violators FROM public.market_hits WHERE seen_at > now() + interval '1 hour'",
    },
    {
        "name": "future_predictions",
        "severity": "critical",
        "threshold": 0,
        "description": "price_predictions.generated_at is in the future",
        "sql": "SELECT COUNT(*) AS violators FROM public.price_predictions WHERE generated_at > now() + interval '1 hour'",
    },
    {
        "name": "ended_before_seen",
        "severity": "warning",
        "threshold": 10,
        "description": "ACTIVE listings with ended_at earlier than seen_at — parsing bug (7d window). Sold-listing comps are excluded because their ended_at IS the historical sale date and is naturally in the past.",
        "sql": """
            SELECT COUNT(*) AS violators FROM public.market_hits
            WHERE seen_at > now() - interval '7 days'
              AND ended_at IS NOT NULL AND seen_at IS NOT NULL
              AND ended_at < seen_at - interval '1 day'
              AND is_listing = true
        """,
    },
    # --- C. Flow-through ---
    {
        "name": "null_item_ref_rate",
        "severity": "warning",
        "threshold": 30,  # alert if >30% of 7d hits have NULL item_ref
        "description": "market_hits with NULL item_ref in last 7d (% of total)",
        "sql": """
            SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE item_ref IS NULL) / NULLIF(COUNT(*), 0), 1)::int AS violators
            FROM public.market_hits WHERE seen_at > now() - interval '7 days'
        """,
    },
    {
        "name": "null_category_rate",
        "severity": "warning",
        "threshold": 15,  # % threshold
        "description": "market_hits with NULL category in last 7d (% of total)",
        "sql": """
            SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE category IS NULL) / NULLIF(COUNT(*), 0), 1)::int AS violators
            FROM public.market_hits WHERE seen_at > now() - interval '7 days'
        """,
    },
    {
        "name": "empty_calibration_snapshots",
        "severity": "warning",
        "threshold": 0,
        "description": "calibration_worker had OK runs but produced 0 snapshots in last 7d",
        "sql": """
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM public.calibration_snapshots WHERE created_at > now() - interval '7 days') = 0
                 AND (SELECT COUNT(*) FROM public.worker_runs
                      WHERE worker_name='calibration_worker'
                        AND finished_at > now() - interval '7 days'
                        AND status='ok') >= 5
                THEN 1 ELSE 0 END AS violators
        """,
    },
    # --- D. Duplication ---
    {
        "name": "duplicate_category_items",
        "severity": "critical",
        "threshold": 0,
        "description": "duplicate (category, item_key) in category_items",
        "sql": """
            SELECT COUNT(*) AS violators FROM (
              SELECT category, item_key FROM public.category_items
              GROUP BY 1,2 HAVING COUNT(*) > 1
            ) d
        """,
    },
    {
        "name": "duplicate_user_settings",
        "severity": "critical",
        "threshold": 0,
        "description": "duplicate user_settings per user_id",
        "sql": """
            SELECT COUNT(*) AS violators FROM (
              SELECT user_id FROM public.user_settings GROUP BY 1 HAVING COUNT(*) > 1
            ) d
        """,
    },
    # --- E. Enum drift ---
    {
        "name": "unknown_worker_status",
        "severity": "warning",
        "threshold": 0,
        "description": "worker_runs.status outside ok/error (e.g. 'partial')",
        "sql": """
            SELECT COUNT(*) AS violators FROM public.worker_runs
            WHERE finished_at > now() - interval '7 days'
              AND status NOT IN ('ok', 'error')
        """,
    },
    # --- F. Data quality ---
    {
        "name": "missing_fx_conversion",
        "severity": "warning",
        "threshold": 100,
        "description": "market_hits with price but NULL price_eur (FX conversion skipped)",
        "sql": """
            SELECT COUNT(*) AS violators FROM public.market_hits
            WHERE price IS NOT NULL AND price > 0 AND price_eur IS NULL
              AND seen_at > now() - interval '7 days'
        """,
    },
    {
        "name": "quantile_outlier_categories",
        "severity": "warning",
        "threshold": 0,
        # 2026-04-25: switched from AVG to MEDIAN denominator — AVG gets
        # dragged up by the very outlier we're trying to detect, masking
        # real Ridge blowups while false-firing on grail items. Comic_books
        # was paging on Incredible Hulk #181 CGC 9.8 @ €140k (legit grail)
        # because AVG = €1,218 was already inflated by it.
        # Also raised the absolute floor from €100k → €1M: grail items in
        # comics/sportscards/watches legitimately reach €100-500k. €1M+ is
        # almost always a model glitch (the 20M clamp already blocks the
        # very largest blow-ups).
        # Median-based: max > 500× median catches Ridge blowups (model
        # outputs €1M+ when nothing similar has been seen).
        "description": "Category with absurd Ridge outlier (>500× median, max>€1M, n>20)",
        "sql": """
            SELECT COUNT(*) AS violators FROM (
              SELECT split_part(item_ref, ':', 1) AS category,
                     COUNT(*) AS n,
                     MAX(q50) AS mx,
                     percentile_cont(0.5) WITHIN GROUP (ORDER BY q50) AS med
              FROM public.price_predictions
              WHERE q50 IS NOT NULL AND generated_at > now() - interval '7 days'
              GROUP BY 1
              HAVING COUNT(*) > 20
                 AND percentile_cont(0.5) WITHIN GROUP (ORDER BY q50) > 100
                 AND MAX(q50) > 1000000
                 AND MAX(q50) / NULLIF(percentile_cont(0.5) WITHIN GROUP (ORDER BY q50), 0) > 500
            ) d
        """,
    },
]


def _cooldown_expired(check_name: str) -> bool:
    last = _last_alerted_at.get(check_name)
    if last is None:
        return True
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed > _ALERT_COOLDOWN_HOURS * 3600


async def _page(failing: list[dict]) -> None:
    try:
        from app.lib.telegram_ops import send_ops_alert
    except Exception:
        return

    lines = ["📊 <b>Daily discovery audit — violations</b>\n"]
    criticals = [f for f in failing if f["severity"] == "critical"]
    warnings = [f for f in failing if f["severity"] == "warning"]

    for f in criticals:
        lines.append(f"🚨 <b>{f['name']}</b>: {f['violators']} rows — {f['description']}")
    for f in warnings:
        lines.append(f"⚠️ <b>{f['name']}</b>: {f['violators']} — {f['description']}")

    lines.append(f"\nAudit run at {datetime.now(timezone.utc).strftime('%H:%M UTC')} "
                  f"({len(failing)} violations)")

    try:
        await send_ops_alert("\n".join(lines))
    except Exception as e:
        logger.warning("discovery_audit: telegram failed: %s", e)


@with_async_retry(max_retries=2, base_delay=2.0, max_delay=60.0)
async def run_once() -> None:
    if not DSN:
        logger.error("DB_DSN not set")
        record_run("discovery_audit_worker", "error")
        return

    # Prefer direct DSN (no pooler 30s cap) — mirrors sanity_probe_worker.
    # SET LOCAL only works in transactions; we want the session-level cap so
    # each fetchrow respects it. Pre-fix the 60s was a no-op and a stuck
    # COUNT on market_hits blocked the whole audit.
    probe_dsn = os.getenv("DB_DSN_DIRECT") or DSN
    conn = await asyncpg.connect(probe_dsn, timeout=20)
    try:
        await conn.execute("SET statement_timeout = '30s'")
    except Exception:
        pass

    failing: list[dict] = []
    try:
        for check in CHECKS:
            try:
                # Double-bound: asyncio cancels the fetch + statement_timeout
                # kills the server-side query. Either one firing stops the
                # hang without dropping the whole audit.
                row = await asyncio.wait_for(
                    conn.fetchrow(check["sql"]),
                    timeout=30.0,
                )
                violators = int(row["violators"] or 0) if row else 0
            except asyncio.TimeoutError:
                logger.warning("discovery_audit %s query timed out (>30s)", check["name"])
                continue
            except Exception as e:
                logger.warning("discovery_audit %s failed: %s", check["name"], e)
                continue

            thresh = check["threshold"]
            if violators > thresh:
                severity = check["severity"]
                logger.warning(
                    "DISCOVERY VIOLATION [%s] %s: %d > %d — %s",
                    severity, check["name"], violators, thresh, check["description"],
                )
                if _cooldown_expired(check["name"]):
                    failing.append({**check, "violators": violators})
                    _last_alerted_at[check["name"]] = datetime.now(timezone.utc)
            else:
                logger.info("discovery_audit %s: %d (≤ threshold %d)",
                            check["name"], violators, thresh)

        if failing:
            await _page(failing)
        else:
            logger.info("discovery_audit: all %d checks clean", len(CHECKS))

    finally:
        await conn.close()
    record_run("discovery_audit_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("discovery_audit_worker", "error")
        log_dead_letter("discovery_audit_worker", {}, e)
        logger.exception("discovery_audit_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
