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

    # Prefer direct DSN — the query joins partitioned market_hits (528K+
    # rows) with watchlist_items via ILIKE, which the pooler's 30s
    # statement_timeout cuts off every cycle. Round-2 fix to the finally
    # clause means these 30s timeouts now correctly record status=error
    # instead of silent ok (23 errors since 19:13 restart, caught by the
    # silent_writer probe). Round-6 routes to DB_DSN_DIRECT so the
    # query actually has time to complete. 2026-04-20.
    probe_dsn = os.getenv("DB_DSN_DIRECT") or DSN
    conn = await asyncpg.connect(probe_dsn)
    # The ILIKE join across 528K+ market_hits + watchlist_items is heavy.
    # Direct DSN already, but Supabase still imposes a default
    # statement_timeout for the role — disable per-session.
    # Bounded 2026-05-04: was unbounded (= 0), which let pathological
    # query plans run for 3+ hours and orphan on bake restart. 600s is the
    # tolerance: a healthy auction_alert cycle is 30-50s, so 10 min is 12x
    # headroom. Above this it's structural — the cycle should fail fast
    # so the supervisor logs error and the next cycle retries cleanly.
    await conn.execute("SET statement_timeout = '600s'")
    alerts_sent = 0

    try:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=ALERT_WINDOW_MINUTES)

        # Find auction listings ending soon that match watchlist items.
        # market_hits columns used: provider, item_ref, url, title, price, ended_at.
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (mh.url)
                mh.id AS hit_id,
                mh.item_ref,
                mh.url,
                mh.price,
                mh.provider,
                mh.ended_at AS end_time,
                mh.title AS listing_title,
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
            WHERE mh.provider IN ('ebay', 'yahoo_auctions', 'catawiki')
              -- Partition prune: alerts only care about recent auctions,
              -- so bound seen_at to the same window the bake crawls.
              -- Without this filter the planner walks all monthly
              -- partitions on every alert tick.
              AND mh.seen_at > now() - interval '14 days'
              AND mh.ended_at IS NOT NULL
              AND mh.ended_at > $1
              AND mh.ended_at <= $2
              AND (mh.is_listing IS NOT TRUE)
              AND NOT EXISTS (
                  SELECT 1 FROM public.alert_trigger_history ath
                  WHERE ath.user_id = wi.user_id
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
            status = "ok"
            return

        logger.info("Found %d auction alerts to send", len(rows))

        from app.lib.notify import notify_user
        import json

        for row in rows:
            user_id = str(row["user_id"])
            listing_title = row["listing_title"] or row["watchlist_title"] or "Auction item"
            price = float(row["price"]) if row["price"] else None
            provider = row["provider"]
            url = row["url"]
            end_time = row["end_time"]
            end_time_str = end_time.isoformat() if end_time else None

            price_str = f" at \u20ac{price:.2f}" if price else ""
            body = (
                f"{listing_title[:60]}{price_str} on {provider} "
                f"\u2014 ending in ~{ALERT_WINDOW_MINUTES} min!"
            )

            # Record alert trigger
            trigger_value = json.dumps({
                "url": url,
                "price": price,
                "provider": provider,
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
                        "provider": provider,
                        "price": price,
                        "end_time": end_time_str,
                    },
                    urgent=True,  # Always send auction alerts
                )
                alerts_sent += 1
            except Exception as push_err:
                logger.debug("Push skipped for auction alert: %s", push_err)

        logger.info("Auction alert cycle: %d alerts sent", alerts_sent)
        status = "ok"

    except Exception as e:
        logger.warning("Auction alert worker error: %s", e, exc_info=True)
        status = "error"
        # 2026-04-24: capture into a name that survives the finally so the
        # error_repr lands in worker_runs.metadata. Previously the metadata
        # was always {} which made these errors loud-but-empty.
        err_repr = f"{type(e).__name__}: {e!s}"[:500]
    finally:
        await conn.close()
        # Record truthful status — previously always 'ok' even when the
        # whole cycle crashed, masking time-critical auction alert failures.
        record_run(
            "auction_alert_worker",
            status if 'status' in locals() else "error",
            error_repr=err_repr if 'err_repr' in locals() else None,
        )


# ---------------------------------------------------------------------------
# Scheduler loop (runs automatically every 5 minutes)
# ---------------------------------------------------------------------------

INTERVAL_SECS = int(os.getenv("AUCTION_ALERT_INTERVAL", "300"))  # 5 minutes

_shutdown = False
_shutdown_event = asyncio.Event()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True
    _shutdown_event.set()


_running = False


async def scheduler_loop():
    """Run the auction alert worker in a loop."""
    global _running
    logger.info(
        "Auction alert scheduler started (interval=%ds)",
        INTERVAL_SECS,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous cycle still running, skipping")
        else:
            _running = True
            try:
                await run_once()
            except Exception as e:
                log_dead_letter("auction_alert_worker", {}, e)
                logger.exception("Auction alert cycle failed: %r", e)
                record_run(
                    "auction_alert_worker", "error",
                    error_repr=f"{type(e).__name__}: {e!s}"[:500],
                )
            finally:
                _running = False

        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=INTERVAL_SECS)
            break
        except asyncio.TimeoutError:
            pass

    logger.info("Auction alert scheduler stopped")


def main():
    import signal as _signal
    _signal.signal(_signal.SIGINT, _handle_signal)
    _signal.signal(_signal.SIGTERM, _handle_signal)

    if not DSN:
        logger.error("DB_DSN not set — cannot start auction alert scheduler")
        import sys
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
