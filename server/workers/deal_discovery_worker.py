#!/usr/bin/env python3
"""Deal discovery worker — scans marketplaces for active purchase mandates.

Follows the same pattern as price_monitor_worker.py:
  - Connects to DB via asyncpg pool
  - Instantiates DealDiscoveryAgent
  - Scans all active mandates
  - Pushes notifications for new qualifying deals
  - Records run in worker registry
"""

import asyncio
import json
import logging
import os
import uuid as _uuid

import asyncpg

from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [deal_discovery] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")


# Plan-gated daily deal alert limits
_FREE_DAILY_DEAL_ALERTS = 1
_PRO_DAILY_DEAL_ALERTS = 999  # effectively unlimited


async def _get_user_deal_alert_count_today(conn, user_id: str) -> int:
    """Count deal alerts sent to user today."""
    row = await conn.fetchrow(
        """
        SELECT count(*) AS cnt FROM public.alert_trigger_history
        WHERE user_id = $1
          AND trigger_type = 'watchlist_snipe'
          AND created_at > now() - interval '24 hours'
        """,
        user_id,
    )
    return row["cnt"] if row else 0


async def _get_user_tier(conn, user_id: str) -> str:
    """Get user subscription tier."""
    row = await conn.fetchrow(
        "SELECT subscription_tier FROM public.user_settings WHERE user_id = $1",
        user_id,
    )
    if row and row["subscription_tier"]:
        return row["subscription_tier"]
    return "free"


async def _check_watchlist_snipes(conn) -> int:
    """Check recent market_hits for listings below watchlist target prices.

    Sends push notifications to users whose watchlist items have active
    listings at or below their target price. Plan-gated: free = 1/day,
    pro/premium = unlimited.

    Returns number of notifications sent.
    """
    # Find watchlist items with target prices that have recent market hits
    # below target. We match by category + fuzzy title match on market_hits.
    rows = await conn.fetch(
        """
        SELECT w.id AS watchlist_id, w.user_id, w.title, w.category,
               w.target_price, w.currency,
               mh.title AS listing_title, mh.price_eur AS listing_price,
               mh.url AS listing_url, mh.provider
        FROM public.watchlist_items w
        JOIN public.market_hits mh
          ON mh.category = w.category
          AND mh.price_eur IS NOT NULL
          AND mh.price_eur > 0
          AND mh.price_eur <= w.target_price
          AND mh.created_at > now() - interval '30 minutes'
        WHERE w.target_price IS NOT NULL
          AND w.target_price > 0
          AND NOT EXISTS (
              SELECT 1 FROM public.alert_trigger_history ath
              WHERE ath.user_id = w.user_id::text
                AND ath.item_id = 'watchlist_snipe:' || w.id::text
                AND ath.trigger_type = 'watchlist_snipe'
                AND ath.created_at > now() - interval '24 hours'
          )
        ORDER BY mh.price_eur ASC
        LIMIT 50
        """
    )

    if not rows:
        return 0

    notified = 0
    user_counts: dict[str, int] = {}

    for row in rows:
        user_id = str(row["user_id"])

        # Plan gating: check daily limit
        if user_id not in user_counts:
            user_counts[user_id] = await _get_user_deal_alert_count_today(conn, user_id)

        tier = await _get_user_tier(conn, user_id)
        limit = _PRO_DAILY_DEAL_ALERTS if tier in ("pro", "premium") else _FREE_DAILY_DEAL_ALERTS
        if user_counts[user_id] >= limit:
            continue

        listing_title = row["listing_title"] or "Item"
        listing_price = float(row["listing_price"])
        target_price = float(row["target_price"])
        discount_pct = ((target_price - listing_price) / target_price) * 100

        message = (
            f"{listing_title[:60]} — \u20ac{listing_price:.2f} "
            f"({discount_pct:.0f}% below your target of \u20ac{target_price:.2f})"
        )

        trigger_value = json.dumps({
            "watchlist_id": str(row["watchlist_id"]),
            "listing_price": listing_price,
            "target_price": target_price,
            "discount_pct": round(discount_pct, 1),
            "listing_url": row["listing_url"],
            "provider": row["provider"],
        })

        item_key = f"watchlist_snipe:{row['watchlist_id']}"

        await conn.execute(
            """
            INSERT INTO public.alert_trigger_history
                (user_id, item_id, trigger_type, trigger_value, message)
            VALUES ($1, $2, 'watchlist_snipe', $3::jsonb, $4)
            """,
            user_id,
            item_key,
            trigger_value,
            message,
        )

        # Send push notification
        try:
            from app.lib.notify import notify_user
            await notify_user(
                conn,
                user_id,
                title="Deal Found!",
                body=message,
                category="deal_alerts",
                data={
                    "type": "watchlist_snipe",
                    "watchlist_id": str(row["watchlist_id"]),
                    "url": row["listing_url"] or "",
                },
            )
        except Exception as push_err:
            logger.debug("Watchlist snipe push failed: %s", push_err)

        user_counts[user_id] = user_counts.get(user_id, 0) + 1
        notified += 1
        logger.info(
            "Watchlist snipe alert: user=%s item=%s price=%.2f target=%.2f",
            user_id[:8], listing_title[:30], listing_price, target_price,
        )

    return notified


def _record_run(status: str) -> None:
    try:
        from app.worker_registry import record_run
        record_run("deal_discovery", status)
    except ImportError:
        pass


@with_async_retry(max_retries=3, base_delay=2.0, max_delay=60.0)
async def run_once():
    """Execute a single deal discovery cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        _record_run("error")
        return

    # Use a connection pool instead of a single raw connection
    pool = await asyncpg.create_pool(DSN, min_size=2, max_size=5)
    logger.info("Connected to DB pool — starting deal discovery cycle")

    status = "ok"
    try:
        from app.agents.deal_discovery_agent import DealDiscoveryAgent
        from app.push import send_push_to_user

        agent = DealDiscoveryAgent()
        try:
            async with pool.acquire() as conn:
                new_deals = await agent.scan_all_active(conn)
        finally:
            await agent.close()

        # Push-notify each new deal (reuse a single connection)
        notified = 0
        async with pool.acquire() as conn:
            for deal in new_deals:
                try:
                    deal_uuid = _uuid.UUID(deal["id"])
                except (ValueError, AttributeError) as exc:
                    logger.warning("[deal_discovery] Invalid deal UUID %r: %s", deal.get("id"), exc)
                    continue

                # Check user preference before sending (P8)
                try:
                    from app.lib.notify import should_notify
                    allowed, reason = await should_notify(conn, deal["user_id"], "deal_alerts")
                    if not allowed:
                        logger.debug("Deal push skipped for user %s: %s", deal["user_id"][:8], reason)
                        continue
                except Exception:
                    pass  # Fallback: send anyway if check fails

                try:
                    sent = await send_push_to_user(
                        conn,
                        deal["user_id"],
                        title="Deal Found!",
                        body=(
                            f"{deal['listing_title'][:60]} \u2014 \u20ac{deal['listing_price']:.2f}"
                            + (f" ({deal.get('discount_pct', 0):.0f}% below market)" if deal.get('discount_pct') else "")
                        ),
                        data={
                            "type": "deal_alert",
                            "deal_id": deal["id"],
                            "url": deal.get("affiliate_url") or deal.get("listing_url", ""),
                        },
                    )
                    if sent > 0:
                        # Mark deal as notified
                        await conn.execute(
                            """
                            UPDATE public.mandate_deals
                            SET status = 'notified', notified_at = now()
                            WHERE id = $1
                            """,
                            deal_uuid,
                        )
                        notified += 1
                except Exception as exc:
                    logger.warning("[deal_discovery] Push failed for deal %s: %s", deal["id"], exc)

        logger.info(
            "Deal discovery cycle complete: %d new deals, %d notified",
            len(new_deals), notified,
        )

        # Phase 2: Watchlist snipe alerts — check recent market_hits against
        # user watchlist_items for deals below target price
        watchlist_notified = 0
        try:
            async with pool.acquire() as conn:
                watchlist_notified = await _check_watchlist_snipes(conn)
        except Exception as wl_exc:
            logger.warning("[deal_discovery] Watchlist snipe check failed: %s", wl_exc)

        logger.info(
            "Deal discovery cycle total: %d mandate deals, %d watchlist snipes",
            notified, watchlist_notified,
        )

    except Exception:
        status = "error"
        raise
    finally:
        await pool.close()
        _record_run(status)


async def main():
    try:
        await run_once()
    except Exception as e:
        log_dead_letter("deal_discovery_worker", {}, e)
        logger.exception("deal_discovery_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
