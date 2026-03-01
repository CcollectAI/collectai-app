#!/usr/bin/env python3
"""Scarcity monitor worker — detects scarce items and alerts owners/watchers.

Runs every 6 hours. Calls detect_scarcity() from data_moat.py and inserts
alert_trigger_history entries for each scarce item (score > 0.5), with dedup
to prevent duplicate alerts.
"""

import asyncio
import json
import logging
import os

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scarcity_monitor] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Only alert on items with scarcity_score above this threshold
SCARCITY_THRESHOLD = 0.5

# Dedup window in hours — don't re-alert same user+item within this window
DEDUP_HOURS = int(os.getenv("SCARCITY_DEDUP_HOURS", "48"))


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    """Execute a single scarcity monitoring cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("scarcity_monitor_worker", "error")
        return

    conn = await asyncpg.connect(DSN)
    logger.info("Connected to DB — starting scarcity monitor cycle")

    try:
        # Import and run scarcity detection
        from app.features.data_moat import detect_scarcity

        scarce_items = await detect_scarcity()

        if not scarce_items:
            logger.info("No scarce items detected")
            return

        # Filter to items above threshold
        actionable = [
            item for item in scarce_items
            if item.get("scarcity_score", 0) > SCARCITY_THRESHOLD
        ]

        if not actionable:
            logger.info(
                "Detected %d items but none above threshold %.2f",
                len(scarce_items), SCARCITY_THRESHOLD,
            )
            return

        logger.info("Found %d scarce items above threshold", len(actionable))
        alerts_fired = 0

        for item in actionable:
            category = item["category"]
            item_key = item["item_key"]
            score = item["scarcity_score"]

            # Find owners and watchers for this item
            interested_users = await conn.fetch(
                """
                SELECT DISTINCT user_id, id::text AS item_id FROM (
                    -- Item owners (match by normalized_key)
                    SELECT user_id, id
                    FROM public.items
                    WHERE normalized_key = $1
                       OR (category = $2 AND normalized_key ILIKE '%' || $1 || '%')

                    UNION

                    -- Watchlist watchers
                    SELECT user_id, id
                    FROM public.watchlist_items
                    WHERE title ILIKE '%' || $1 || '%'
                      AND category = $2
                ) sub
                """,
                item_key,
                category,
            )

            if not interested_users:
                continue

            for user_row in interested_users:
                user_id = user_row["user_id"]
                item_id = str(user_row["item_id"])

                # Dedup check — don't fire if already alerted recently
                already = await conn.fetchrow(
                    """
                    SELECT 1 FROM public.alert_trigger_history
                    WHERE user_id = $1
                      AND item_id = $2
                      AND trigger_type = 'scarcity'
                      AND created_at > now() - ($3 || ' hours')::interval
                    LIMIT 1
                    """,
                    user_id,
                    item_id,
                    str(DEDUP_HOURS),
                )

                if already:
                    continue

                trigger_value = json.dumps({
                    "scarcity_score": score,
                    "demand_growth_pct": item.get("demand_growth_pct", 0),
                    "supply_decline_pct": item.get("supply_decline_pct", 0),
                    "recent_demand": item.get("recent_demand", 0),
                    "recent_supply": item.get("recent_supply"),
                })

                message = (
                    f"Scarcity alert: {item_key} ({category}) — "
                    f"supply declining while demand rising "
                    f"(score: {score:.2f})"
                )

                await conn.execute(
                    """
                    INSERT INTO public.alert_trigger_history
                        (user_id, item_id, trigger_type, trigger_value, message)
                    VALUES ($1, $2, 'scarcity', $3::jsonb, $4)
                    """,
                    user_id,
                    item_id,
                    trigger_value,
                    message,
                )

                alerts_fired += 1
                logger.info(
                    "Scarcity alert fired: user=%s item_key=%s score=%.2f",
                    user_id, item_key, score,
                )

        logger.info(
            "Scarcity monitor cycle complete: %d scarce items, %d alerts fired",
            len(actionable), alerts_fired,
        )

    finally:
        await conn.close()
        record_run("scarcity_monitor_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("scarcity_monitor_worker", "error")
        log_dead_letter("scarcity_monitor_worker", {}, e)
        logger.exception("scarcity_monitor_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
