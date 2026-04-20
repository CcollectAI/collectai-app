#!/usr/bin/env python3
"""Watchlist monitor worker — bridges watchlist → MarketplaceAgent → market_hits.

Scans watchlist items due for a market check, runs aggregate_search via
the existing MarketplaceAgent, persists comps to market_hits (so the
valuation_worker + price_monitor_worker pick them up automatically),
and updates watchlist rows with latest pricing/trend data.

If a watchlist item's target price is met (market price ≤ target),
an alert is fired to alert_trigger_history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
from datetime import datetime, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchlist_monitor] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# How many watchlist items to scan per cycle
BATCH_SIZE = int(os.getenv("WATCHLIST_MONITOR_BATCH", "100"))

# Dedup window for target-met alerts (hours)
DEDUP_HOURS = int(os.getenv("WATCHLIST_ALERT_DEDUP_HOURS", "24"))

# Priority tier intervals (minutes)
HIGH_PRIORITY_INTERVAL = 15   # Items within 10% of target
MEDIUM_PRIORITY_INTERVAL = 60  # Standard watchlist items
LOW_PRIORITY_INTERVAL = 360    # Items far from target (>50% away)

# Batch sizes per priority
HIGH_PRIORITY_BATCH = 20


def _compute_priority(target_price: float | None, market_price: float | None) -> str:
    """Compute scan priority based on how close market price is to target."""
    if target_price is None or market_price is None:
        return "medium"
    if market_price <= 0:
        return "medium"
    diff_pct = abs(market_price - target_price) / target_price * 100
    if diff_pct <= 10:
        return "high"    # Within 10% of target — scan frequently
    elif diff_pct <= 50:
        return "medium"  # Moderate distance
    return "low"          # Far from target — scan less often


async def _already_fired(conn, user_id: str, item_key: str) -> bool:
    """Check if a watchlist_target_met alert fired recently for this user+item."""
    row = await conn.fetchrow(
        """
        SELECT 1 FROM public.alert_trigger_history
        WHERE user_id = $1
          AND item_id = $2
          AND trigger_type = 'watchlist_target_met'
          AND created_at > now() - ($3 || ' hours')::interval
        LIMIT 1
        """,
        user_id,
        item_key,
        str(DEDUP_HOURS),
    )
    return row is not None


def _determine_trend(old_price: float | None, new_price: float) -> str:
    """Compare old and new price to determine trend direction."""
    if old_price is None:
        return "stable"
    diff_pct = ((new_price - old_price) / old_price) * 100 if old_price != 0 else 0
    if diff_pct > 2.0:
        return "up"
    elif diff_pct < -2.0:
        return "down"
    return "stable"


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    """Execute a single watchlist monitoring cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("watchlist_monitor_worker", "error")
        return

    # Lazy import to avoid circular deps at module level
    from app.agents.marketplace_agent import MarketplaceAgent
    from app.features.data_moat import record_supply_snapshot

    conn = await asyncpg.connect(DSN)
    logger.info("Connected to DB — starting watchlist monitor cycle")

    # R46.15 guard removed — last_market_price + last_checked_at columns
    # now exist on watchlist_items (added in R49).

    agent = MarketplaceAgent()
    scanned = 0
    alerts_fired = 0

    try:
        # Pass 1: High-priority items (near target, scan every 15min)
        high_rows = await conn.fetch(
            """
            SELECT id, user_id, title, category,
                   target_price, currency, last_market_price
            FROM public.watchlist_items
            WHERE target_price IS NOT NULL
              AND last_market_price IS NOT NULL
              AND last_market_price > 0
              AND target_price > 0
              AND abs(last_market_price - target_price) / target_price <= 0.10
              AND (last_checked_at IS NULL
                   OR last_checked_at < now() - interval '15 minutes')
            ORDER BY last_checked_at ASC NULLS FIRST
            LIMIT $1
            """,
            HIGH_PRIORITY_BATCH,
        )

        # Pass 2: Standard items (everything else, normal cycle)
        remaining_budget = BATCH_SIZE - len(high_rows)
        standard_rows = await conn.fetch(
            """
            SELECT id, user_id, title, category,
                   target_price, currency, last_market_price
            FROM public.watchlist_items
            WHERE (last_checked_at IS NULL
                   OR last_checked_at < now() - interval '1 hour')
            ORDER BY last_checked_at ASC NULLS FIRST
            LIMIT $1
            """,
            max(remaining_budget, 0),
        )

        rows = list(high_rows) + list(standard_rows)

        # Deduplicate by id
        seen_ids = set()
        deduped_rows = []
        for r in rows:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                deduped_rows.append(r)
        rows = deduped_rows

        if not rows:
            logger.info("No watchlist items to scan")
            record_run("watchlist_monitor_worker", "ok")
            return

        logger.info(
            "Scanning %d watchlist items (%d high-priority, %d standard)",
            len(rows), len(high_rows), len(standard_rows),
        )

        per_item_failures = 0

        for row in rows:
            wl_id = row["id"]  # UUID — keep as-is for asyncpg
            user_id = str(row["user_id"])
            title = row["title"]
            category = row["category"]
            target_price = float(row["target_price"]) if row["target_price"] is not None else None
            old_market_price = float(row["last_market_price"]) if row["last_market_price"] is not None else None

            search_query = title or f"collectible {category or 'item'}"

            try:
                # Use existing MarketplaceAgent for aggregated search
                result = await agent.aggregate_search(
                    query=search_query,
                    category=category,
                    limit=20,
                    include_sold=True,
                )

                # Persist hits to market_hits (valuation_worker picks these up)
                normalized_key = title.lower().strip().replace(" ", "_") if title else None
                await agent.persist_comps_to_db(result, normalized_key=normalized_key, category=category)

                # Compute median price from top provenance hits
                prices = [
                    float(h.hit.get("price", 0))
                    for h in result.hits
                    if h.hit.get("price") is not None and float(h.hit.get("price", 0)) > 0
                ]

                current_price = statistics.median(prices) if prices else None
                hit_count = len(result.hits)
                trend = _determine_trend(old_market_price, current_price) if current_price else "stable"

                # Update watchlist row
                await conn.execute(
                    """
                    UPDATE public.watchlist_items
                    SET last_market_price = $1,
                        last_checked_at = $2,
                        price_trend = $3,
                        market_hit_count = $4
                    WHERE id = $5
                    """,
                    current_price,
                    datetime.now(timezone.utc),
                    trend,
                    hit_count,
                    wl_id,
                )

                # Record supply snapshot (data moat)
                if current_price and category:
                    avg_p = statistics.mean(prices) if prices else None
                    min_p = min(prices) if prices else None
                    max_p = max(prices) if prices else None
                    await record_supply_snapshot(
                        category=category,
                        item_key=normalized_key or search_query,
                        listing_count=hit_count,
                        avg_price_eur=avg_p,
                        min_price_eur=min_p,
                        max_price_eur=max_p,
                        source="watchlist_monitor",
                    )

                # Fire alert if market price drops to or below target
                if (
                    current_price is not None
                    and target_price is not None
                    and current_price <= target_price
                ):
                    item_key = f"watchlist:{wl_id}"
                    if not await _already_fired(conn, user_id, item_key):
                        trigger_value = json.dumps({
                            "current_price": round(current_price, 2),
                            "target_price": round(target_price, 2),
                            "hit_count": hit_count,
                            "watchlist_id": str(wl_id),
                        })
                        message = (
                            f"{title or 'Watchlist item'} is now at "
                            f"{current_price:.2f}, below your target of "
                            f"{target_price:.2f}"
                        )
                        await conn.execute(
                            """
                            INSERT INTO public.alert_trigger_history
                                (user_id, item_id, trigger_type, trigger_value, message)
                            VALUES ($1, $2, 'watchlist_target_met', $3::jsonb, $4)
                            """,
                            user_id,
                            item_key,
                            trigger_value,
                            message,
                        )
                        alerts_fired += 1

                        # Send push notification (P0)
                        try:
                            from app.lib.notify import notify_user
                            await notify_user(
                                conn,
                                user_id,
                                title="\ud83c\udfaf Target Price Met!",
                                body=message,
                                category="price_alerts",
                                data={
                                    "type": "watchlist_target_met",
                                    "watchlist_id": str(wl_id),
                                    "current_price": round(current_price, 2),
                                    "target_price": round(target_price, 2),
                                },
                                urgent=True,  # Target met = urgent
                            )
                        except Exception as push_err:
                            logger.debug("Push skipped for watchlist alert: %s", push_err)

                        logger.info(
                            "Target met alert: wl=%s price=%.2f target=%.2f",
                            wl_id, current_price, target_price,
                        )

                scanned += 1

            except Exception as e:
                per_item_failures += 1
                logger.warning(
                    "Failed to scan watchlist item %s: %s", str(wl_id), e,
                    exc_info=True,
                )

        logger.info(
            "Watchlist monitor cycle complete: scanned=%d alerts=%d failures=%d",
            scanned, alerts_fired, per_item_failures,
        )
        # If the entire batch failed item-by-item, don't call it 'ok'.
        # Partial failures still count as ok (some items scanned) so the
        # overdue-alert doesn't spam every cycle when an intermittent
        # source is flaky.
        if per_item_failures and scanned == 0:
            cycle_status = "error"
        else:
            cycle_status = "ok"

    finally:
        await agent.close()
        await conn.close()
        record_run("watchlist_monitor_worker", cycle_status if "cycle_status" in locals() else "error")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("watchlist_monitor_worker", "error")
        log_dead_letter("watchlist_monitor_worker", {}, e)
        logger.exception("watchlist_monitor_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
