#!/usr/bin/env python3
"""Simple alerts worker — checks for low-value items and creates alerts.

This is a lightweight supplement to the full price_monitor_worker.
It scans recent price_predictions and fires basic low-value alerts
into alert_trigger_history.

Performance: uses a single batched query with JOINs instead of per-item
lookups (eliminates N+1 problem — was up to 151 sequential queries).
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

# Single batched query: fetches the latest prediction per item, joins with
# items to get the owner, filters for low-value (q50 < 10), and excludes
# items that already had a low_value alert fired in the last 24 hours.
_BATCH_QUERY = """
SELECT DISTINCT ON (pp.item_ref)
    pp.item_ref,
    -- The OWNED row's uuid. alert_trigger_history.item_id is `text`, so writing
    -- pp.item_ref (a catalog key like `pokemon:base1-base1-99`) into it was
    -- accepted by Postgres but broke every consumer: the alerts screen and the
    -- push deep-link both feed item_id into /item/[id], which is keyed by
    -- items.id (uuid) and 22P02s on a catalog key. 58/58 non-null rows written
    -- by this worker were unusable. The join already has the real id — use it.
    i.id AS item_uuid,
    pp.q10,
    pp.q50,
    pp.q90,
    i.user_id
FROM public.price_predictions pp
JOIN public.items i ON i.canonical_key = pp.item_ref
WHERE pp.q50 IS NOT NULL
  AND pp.q50 < 10
  AND pp.item_ref IS NOT NULL
  AND i.user_id IS NOT NULL
  -- Partition prune: only the latest prediction per item matters for
  -- alerting, and predictions regenerate weekly. Without this the
  -- planner walks all monthly partitions on every alert cycle.
  AND pp.generated_at > now() - interval '30 days'
  AND NOT EXISTS (
      SELECT 1 FROM public.alert_trigger_history ath
      WHERE ath.user_id = i.user_id
        -- Must match what the INSERT below writes (items.id as text), not
        -- pp.item_ref — otherwise the 24h dedup silently never matches and the
        -- same item re-alerts every cycle.
        AND ath.item_id = i.id::text
        AND ath.trigger_type = 'low_value'
        AND ath.created_at > now() - interval '24 hours'
  )
ORDER BY pp.item_ref, pp.generated_at DESC
LIMIT 50
"""


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    if not DSN:
        logger.error("No DB_DSN env")
        return

    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(_BATCH_QUERY)

        fired = 0
        for r in rows:
            # item_id must be the items uuid — it is what the alerts screen and
            # the push handler route on. item_ref (the catalog key) stays in the
            # message text, where it is human-readable and harmless.
            item_id = str(r["item_uuid"])
            item_ref = r["item_ref"]
            owner = r["user_id"]
            mid = r["q50"]

            trigger_value = json.dumps({
                "current_price": float(mid),
                "q10": float(r["q10"]) if r["q10"] is not None else None,
                "q90": float(r["q90"]) if r["q90"] is not None else None,
            })
            message = f"Low valuation alert: item {item_ref} estimated at {mid:.2f} EUR"

            await conn.execute("""
                INSERT INTO public.alert_trigger_history
                    (user_id, item_id, trigger_type, trigger_value, message)
                VALUES ($1, $2, 'low_value', $3::jsonb, $4)
            """, owner, str(item_id), trigger_value, message)

            # Send push notification to user (preference-aware)
            try:
                from app.lib.notify import notify_user
                await notify_user(
                    conn, owner, "Price Alert", message,
                    category="price_alerts",
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
