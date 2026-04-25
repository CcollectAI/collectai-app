#!/usr/bin/env python3
"""Vision regret worker — turns delete/archive signals into per-category
training emphasis for the next vision retraining cycle.

Closes the loop:
  user adds via AI scan → user deletes/archives shortly after
  → vision_regret_worker computes regret_rate per category
  → model_retrain_worker._export_scan_corrections multiplies user_weight
    by `1 + regret_rate * 2` for that category, so corrections from
    high-error categories train faster
  → next vision_reclassifier_worker cycle has stronger signal on the
    failure modes

Data shape (verified 2026-04-26):
  - items.id is UUID, items.source ∈ {ai|scan|manual}, items.created_at
  - demand_signals(item_deleted/item_archived).item_key is items.id::text
    (set by commit 59c3c2f patches at items_router batch-delete/archive).
  - demand_signals(item_added) would be cleaner but isn't wired today —
    instead we use items.created_at + items.source as the "added by AI" set.
  - predict_sessions.item_id is BIGINT and NULL in samples; do NOT join
    via that column.

A regret event = an AI/scan-sourced item created in the last 30 days
that received an item_deleted or item_archived signal within REGRET_WINDOW
days of being created.

Gates: nothing useful until items + delete signals exist. Worker exits
cleanly with `regret_rate=null` when sample size is below MIN_ITEMS_PER_CAT.
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from app.worker_registry import record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vision_regret] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
LOOKBACK_DAYS = int(os.getenv("VISION_REGRET_LOOKBACK_DAYS", "30"))
REGRET_WINDOW_DAYS = int(os.getenv("VISION_REGRET_WINDOW_DAYS", "7"))
MIN_ITEMS_PER_CAT = int(os.getenv("VISION_REGRET_MIN_ITEMS", "10"))


async def _ensure_table(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public.vision_category_regret (
            category         text PRIMARY KEY,
            regret_rate_30d  numeric,    -- 0.0-1.0; deletes_within_7d / total_added
            items_added      integer,
            items_regretted  integer,
            computed_at      timestamptz NOT NULL DEFAULT now()
        )
        """
    )


async def run_once() -> dict[str, int]:
    if not DSN:
        logger.warning("DB_DSN not set — skipping")
        record_run("vision_regret_worker", "error")
        return {"updated": 0}

    conn = await asyncpg.connect(DSN)
    updated = 0
    skipped = 0
    try:
        await _ensure_table(conn)

        # For each category, count items created via AI/scan in last LOOKBACK
        # AND count which of those received a delete/archive signal within
        # REGRET_WINDOW days of created_at. Single grouped query.
        rows = await conn.fetch(
            """
            WITH ai_items AS (
                SELECT id::text AS item_key, category, created_at
                FROM public.items
                WHERE source IN ('ai', 'scan')
                  AND created_at >= now() - ($1 || ' days')::interval
                  AND category IS NOT NULL
            ),
            regret_events AS (
                SELECT DISTINCT ds.item_key
                FROM public.demand_signals ds
                JOIN ai_items ai ON ai.item_key = ds.item_key
                WHERE ds.signal_type IN ('item_deleted', 'item_archived')
                  AND ds.created_at <= ai.created_at + ($2 || ' days')::interval
                  AND ds.created_at >= ai.created_at
            )
            SELECT
                ai.category,
                COUNT(*) AS items_added,
                COUNT(*) FILTER (WHERE re.item_key IS NOT NULL) AS items_regretted
            FROM ai_items ai
            LEFT JOIN regret_events re ON re.item_key = ai.item_key
            GROUP BY ai.category
            """,
            str(LOOKBACK_DAYS), str(REGRET_WINDOW_DAYS),
        )

        if not rows:
            logger.info("No AI/scan items in last %dd — nothing to compute", LOOKBACK_DAYS)
            record_run("vision_regret_worker", "ok")
            return {"updated": 0, "skipped": 0}

        for r in rows:
            category = r["category"]
            n_added = int(r["items_added"])
            n_regretted = int(r["items_regretted"])
            if n_added < MIN_ITEMS_PER_CAT:
                skipped += 1
                continue
            regret_rate = n_regretted / n_added if n_added else 0.0
            await conn.execute(
                """
                INSERT INTO public.vision_category_regret
                    (category, regret_rate_30d, items_added,
                     items_regretted, computed_at)
                VALUES ($1, $2, $3, $4, now())
                ON CONFLICT (category) DO UPDATE SET
                    regret_rate_30d = EXCLUDED.regret_rate_30d,
                    items_added     = EXCLUDED.items_added,
                    items_regretted = EXCLUDED.items_regretted,
                    computed_at     = now()
                """,
                category, regret_rate, n_added, n_regretted,
            )
            updated += 1
            logger.info(
                "  %s: added=%d regretted=%d rate=%.3f",
                category, n_added, n_regretted, regret_rate,
            )

        logger.info(
            "vision_regret cycle complete: updated=%d skipped=%d (lookback=%dd, window=%dd)",
            updated, skipped, LOOKBACK_DAYS, REGRET_WINDOW_DAYS,
        )
        record_run("vision_regret_worker", "ok")
        return {"updated": updated, "skipped": skipped}
    finally:
        await conn.close()


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("vision_regret_worker", "error")
        logger.exception("vision_regret_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
