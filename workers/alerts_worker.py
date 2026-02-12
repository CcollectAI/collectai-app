#!/usr/bin/env python3
"""Simple alerts worker — checks for low-value items and creates alerts.

This is a lightweight supplement to the full price_monitor_worker.
It scans recent price_predictions and fires basic low-value alerts
into alert_trigger_history.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [alerts_worker] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    if not DSN:
        logger.error("No DB_DSN env")
        return

    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (item_id)
                   item_id, q10, q50, q90
            FROM public.price_predictions
            ORDER BY item_id, asof DESC
            LIMIT 50
        """)

        fired = 0
        for r in rows:
            item_id = r["item_id"]
            mid = r["q50"]

            if mid is None:
                continue

            if mid < 10:
                # Find owner of this item
                owner = await conn.fetchval(
                    "SELECT user_id FROM public.items WHERE id = $1",
                    item_id,
                )
                if not owner:
                    continue

                trigger_value = json.dumps({
                    "current_price": float(mid),
                    "q10": float(r["q10"]) if r["q10"] is not None else None,
                    "q90": float(r["q90"]) if r["q90"] is not None else None,
                })
                message = f"Low valuation alert: item {item_id} estimated at {mid:.2f} EUR"

                await conn.execute("""
                    INSERT INTO public.alert_trigger_history
                        (user_id, item_id, trigger_type, trigger_value, message)
                    VALUES ($1, $2, 'low_value', $3::jsonb, $4)
                """, owner, str(item_id), trigger_value, message)

                # Send push notification to user
                try:
                    from app.push import send_push_to_user
                    await send_push_to_user(
                        conn,
                        owner,
                        "Price Alert",
                        message,
                        data={"type": "price_alert", "item_id": str(item_id)},
                    )
                except Exception as push_err:
                    logger.debug("Push notification skipped: %s", push_err)

                fired += 1
                logger.info(message)

        logger.info("Alerts worker complete: %d alerts fired", fired)
    finally:
        await conn.close()
    record_run("alerts_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("alerts_worker", "error")
        log_dead_letter("alerts_worker", {}, e)
        logger.exception("alerts_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
