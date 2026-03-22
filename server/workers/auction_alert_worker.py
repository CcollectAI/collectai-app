#!/usr/bin/env python3
"""Auction end-time alert worker — notifies users when watched auctions are ending soon.

Scans market_hits for eBay/Yahoo Auctions listings with end_time within the next
15 minutes that match items on user watchlists, and sends urgent push notifications.

Runs every 5 minutes.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [auction_alert] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Alert window: notify when auction ends within this many minutes
ALERT_WINDOW_MINUTES = int(os.getenv("AUCTION_ALERT_WINDOW", "15"))

# Dedup: don't alert same user for same listing twice
DEDUP_HOURS = 4


@with_async_retry(max_retries=2, base_delay=1.0, max_delay=30.0)
async def run_once():
    """Execute a single auction alert cycle."""
    if not DSN:
        logger.error("DB_DSN not set")
        record_run("auction_alert_worker", "error")
        return

    conn = await asyncpg.connect(DSN)
    alerts_sent = 0

    try:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=ALERT_WINDOW_MINUTES)

        # Find auction listings ending soon that match watchlist items
        # market_hits has: source, item_ref, url, price, extra_json (which may contain end_time/sold_at)
        # We check extra_json->>'end_time' or the sold_at field for auction end times
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (mh.url)
                mh.id AS hit_id,
                mh.item_ref,
                mh.url,
                mh.price,
                mh.source,
                mh.extra_json->>'end_time' AS end_time_str,
                mh.extra_json->>'title' AS listing_title,
                wi.user_id,
                wi.title AS watchlist_title,
                wi.id AS watchlist_id,
                wi.target_price
            FROM public.market_hits mh
            JOIN public.watchlist_items wi
                ON (
                    mh.item_ref IS NOT NULL
                    AND (
                        wi.title ILIKE '%%' || mh.item_ref || '%%'
                        OR mh.item_ref ILIKE '%%' || REPLACE(wi.title, ' ', '_') || '%%'
                    )
                )
            WHERE mh.source IN ('ebay', 'yahoo_auctions', 'catawiki')
              AND mh.extra_json->>'end_time' IS NOT NULL
              AND (mh.extra_json->>'end_time')::timestamptz > $1
              AND (mh.extra_json->>'end_time')::timestamptz <= $2
              AND NOT EXISTS (
                  SELECT 1 FROM public.alert_trigger_history ath
                  WHERE ath.user_id = wi.user_id::text
                    AND ath.item_id = mh.url
                    AND ath.trigger_type = 'auction_ending'
                    AND ath.created_at > now() - ($3 || ' hours')::interval
              )
            LIMIT 50
            """,
            now,
            window_end,
            str(DEDUP_HOURS),
        )

        if not rows:
            logger.info("No auctions ending in the next %d minutes", ALERT_WINDOW_MINUTES)
            record_run("auction_alert_worker", "ok")
            return

        logger.info("Found %d auction alerts to send", len(rows))

        from app.lib.notify import notify_user
        import json

        for row in rows:
            user_id = str(row["user_id"])
            listing_title = row["listing_title"] or row["watchlist_title"] or "Auction item"
            price = float(row["price"]) if row["price"] else None
            source = row["source"]
            url = row["url"]
            end_time_str = row["end_time_str"]

            price_str = f" at \u20ac{price:.2f}" if price else ""
            body = (
                f"{listing_title[:60]}{price_str} on {source} "
                f"\u2014 ending in ~{ALERT_WINDOW_MINUTES} min!"
            )

            # Record alert trigger
            trigger_value = json.dumps({
                "url": url,
                "price": price,
                "source": source,
                "end_time": end_time_str,
                "watchlist_id": str(row["watchlist_id"]),
            })

            await conn.execute(
                """
                INSERT INTO public.alert_trigger_history
                    (user_id, item_id, trigger_type, trigger_value, message)
                VALUES ($1, $2, 'auction_ending', $3::jsonb, $4)
                """,
                user_id,
                url,  # Use URL as item_id for dedup
                trigger_value,
                body,
            )

            # Send urgent push
            try:
                await notify_user(
                    conn,
                    user_id,
                    title="Auction Ending Soon!",
                    body=body,
                    category="price_alerts",
                    data={
                        "type": "auction_ending",
                        "url": url,
                        "source": source,
                        "price": price,
                        "end_time": end_time_str,
                    },
                    urgent=True,  # Always send auction alerts
                )
                alerts_sent += 1
            except Exception as push_err:
                logger.debug("Push skipped for auction alert: %s", push_err)

        logger.info("Auction alert cycle: %d alerts sent", alerts_sent)

    except Exception as e:
        logger.warning("Auction alert worker error: %s", e, exc_info=True)
    finally:
        await conn.close()
        record_run("auction_alert_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("auction_alert_worker", "error")
        log_dead_letter("auction_alert_worker", {}, e)
        logger.exception("auction_alert_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
