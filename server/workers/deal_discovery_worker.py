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
    """Get user subscription tier from the canonical subscriptions table.

    Pre-2026-05-02 this read user_settings.subscription_tier — but that
    column is never populated (canonical source is `subscriptions.plan`,
    written by the Stripe webhook). Result: every user came back as
    'free', and every paid user was capped at 1 deal alert/day instead
    of the documented unlimited.
    """
    row = await conn.fetchrow(
        "SELECT plan FROM public.subscriptions "
        "WHERE user_id = $1::uuid AND status IN ('active', 'trialing') "
        "LIMIT 1",
        user_id,
    )
    return row["plan"] if row else "free"


# Minimum trigram similarity for the title fallback. Watchlist rows added as
# free text have no catalog id, so the only handle on identity is the title.
# 0.55 keeps "Bayou" from matching "Bayou Dragon"-style near-misses while still
# tolerating the condition/finish suffixes marketplaces append.
_TITLE_MATCH_THRESHOLD = 0.55

# Titles that carry no identity. Legacy watchlist rows predating the 2026-06-05
# name-vs-title fix are literally "(unnamed)"; searching on that matched
# everything (see docs/alerts-and-insights.md).
_UNUSABLE_TITLES = ("(unnamed)", "")


async def _check_watchlist_snipes(conn) -> int:
    """Check recent market_hits for *buyable* listings below watchlist targets.

    Sends push notifications to users whose watchlist items have active
    listings at or below their target price. Plan-gated: free = 1/day,
    pro/premium = unlimited.

    Three conditions define a snipe, and the original query had none of them:

    1. **It must be the same item.** The join used to be `mh.category =
       w.category` alone — the docstring claimed a fuzzy title match that was
       never in the SQL. Any listing in the category under the target fired, so
       a €8015 target on an MTG dual land alerted on a €0.02 common. Identity
       now comes from `watchlist_items.item_id`, which holds a **bare**
       canonical key (`sum-283-bayou`) while `market_hits.item_ref` is
       **namespaced** (`mtg:sum-283-bayou`) — hence the concatenation. See
       learning_canonical_key_vs_item_ref_namespace. Free-text rows with no
       item_id fall back to a trigram title match within the category.

    2. **It must be buyable.** `url IS NOT NULL AND is_listing IS TRUE`. Most
       market_hits are price observations, not offers: of 276k rows in the last
       two days only 35k carried a URL, and the MTG ones are Scryfall price
       rows. An alert with no link renders as a dead "View Item" button and
       still burns the user's one free alert for the day.

    3. **It must be cheaper than the target**, which was already true.

    Returns number of notifications sent.
    """
    rows = await conn.fetch(
        """
        SELECT w.id AS watchlist_id, w.user_id, w.title, w.category,
               w.target_price, w.currency,
               mh.title AS listing_title, mh.price_eur AS listing_price,
               mh.url AS listing_url, mh.provider
        FROM public.watchlist_items w
        JOIN public.market_hits mh
          ON mh.seen_at > now() - interval '30 minutes'
          AND mh.price_eur IS NOT NULL
          AND mh.price_eur > 0
          AND mh.price_eur <= w.target_price
          -- Buyable, not merely observed: a price row is not an offer.
          AND mh.url IS NOT NULL
          AND mh.is_listing IS TRUE
          AND (
              -- Exact catalog identity. item_id is bare, item_ref namespaced.
              (w.item_id IS NOT NULL AND mh.item_ref = w.category || ':' || w.item_id)
              -- Fallback for free-text watchlist rows: same category, and the
              -- listing title actually looks like the thing being watched.
              OR (
                  w.item_id IS NULL
                  AND mh.category = w.category
                  AND similarity(mh.title, w.title) >= $1
              )
          )
        WHERE w.target_price IS NOT NULL
          AND w.target_price > 0
          AND w.title IS NOT NULL
          AND w.title <> ALL($2::text[])
          AND length(w.title) >= 3
          AND NOT EXISTS (
              SELECT 1 FROM public.alert_trigger_history ath
              WHERE ath.user_id = w.user_id
                AND ath.item_id = 'watchlist_snipe:' || w.id::text
                AND ath.trigger_type = 'watchlist_snipe'
                AND ath.created_at > now() - interval '24 hours'
          )
        ORDER BY mh.price_eur ASC
        LIMIT 50
        """,
        _TITLE_MATCH_THRESHOLD,
        list(_UNUSABLE_TITLES),
    )

    if not rows:
        return 0

    # Deferred import, like the notify_user one below: `app.*` modules pull in
    # config/DB at import time, and this worker must stay importable standalone.
    from app.lib.affiliate import build_affiliate_url

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
        provider = row["provider"] or "Marketplace"

        # Tag once and reuse for BOTH surfaces. app/alerts.tsx:339 opens
        # `affiliate_url || listing_url`, so without this the Alerts screen
        # opened the raw URL and earned nothing while the push notification
        # (which gets the tagged one as its deep_link) did.
        listing_url = row["listing_url"] or ""
        affiliate_url = ""
        if listing_url:
            affiliate_url, _ = build_affiliate_url(
                listing_url, provider, subid=str(row["watchlist_id"])
            )

        message = (
            f"{listing_title[:60]} — \u20ac{listing_price:.2f} on {provider} "
            f"({discount_pct:.0f}% below your target of \u20ac{target_price:.2f})"
        )

        trigger_value = json.dumps({
            "watchlist_id": str(row["watchlist_id"]),
            "listing_price": listing_price,
            "target_price": target_price,
            "discount_pct": round(discount_pct, 1),
            "listing_url": listing_url,
            "affiliate_url": affiliate_url or listing_url,
            "provider": provider,
            # app/alerts.tsx reads `listing_source` for the button label and
            # falls back to the literal word "Marketplace". Only `provider` was
            # ever written, so every snipe alert said "View on Marketplace".
            "listing_source": provider,
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

        # Send push notification.
        #
        # `deep_link` is what makes the row in app/notifications.tsx do
        # something: handleTap navigates only when it is set, and MEASURED
        # 2026-08-04 every one of the 11 notification_history rows in prod had
        # deep_link NULL — so the whole notifications screen was tap-to-nothing.
        # A snipe's destination is the listing itself, affiliate-tagged so the
        # click is attributable and earns.
        try:
            from app.lib.notify import notify_user

            deep_link = affiliate_url or listing_url or None

            await notify_user(
                conn,
                user_id,
                title="Deal Found!",
                body=message,
                category="deal_alerts",
                deep_link=deep_link,
                data={
                    "type": "watchlist_snipe",
                    "watchlist_id": str(row["watchlist_id"]),
                    "url": deep_link or listing_url,
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
            # D1/D4: pass the pool so the agent acquires a connection per mandate
            # rather than holding one for the entire 50-mandate serial cycle.
            new_deals = await agent.scan_all_active(pool)
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
