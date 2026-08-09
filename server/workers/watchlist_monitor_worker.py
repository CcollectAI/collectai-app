#!/usr/bin/env python3
"""Watchlist monitor worker — demand-driven market supply for watched items.

Scans watchlist items due for a market check, runs aggregate_search via the
existing MarketplaceAgent, persists comps to market_hits, and updates watchlist
rows with latest pricing/trend data.

**It does not alert.** As of 2026-08-06 the only "your target was hit" alert is
deal_discovery_worker's snipe, which requires a live, buyable listing. See the
long comment at the old alert site below.

Why it still exists: it is the only path that fetches market data *because a
user asked for it*, rather than by walking the catalog. marketplace_scrape_
scheduler.SKIP_CATEGORIES excludes mtg/pokemon/yugioh (their bulk price feeds
already give "coverage"), and those three categories had 0 buyable listings out
of 609k rows on 2026-08-06 — so nothing there can ever produce a snipe. Watched
items are tens, not the 80k TCG catalog, which is what keeps the outbound
request volume bounded.
"""

from __future__ import annotations

import asyncio
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

    # Prefer direct DSN — watchlist monitor aggregates over all watchlist
    # items + runs marketplace lookups per item; the pooler's 30s cap is
    # easy to hit with 50+ watchlist entries. Round 7 2026-04-20.
    conn = await asyncpg.connect(os.getenv("DB_DSN_DIRECT") or DSN)
    logger.info("Connected to DB — starting watchlist monitor cycle")

    # R46.15 guard removed — last_market_price + last_checked_at columns
    # now exist on watchlist_items (added in R49).

    agent = MarketplaceAgent()
    scanned = 0

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
            cycle_status = "ok"
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

                # NO ALERT IS FIRED HERE \u2014 deliberately, since 2026-08-06.
                #
                # This worker used to also insert `watchlist_target_met` and
                # push "\ud83c\udfaf Target Price Met!". That is the same promise the
                # snipe makes (deal_discovery_worker._check_watchlist_snipes),
                # from weaker evidence: this fires on a *computed median* of
                # recent comps, so it can wake a user for something that is not
                # for sale anywhere. The snipe requires a live listing with a
                # URL and `is_listing = true`, so its alert always has a buy
                # button at the end of it.
                #
                # Two workers answering "has my target been hit?" also meant two
                # dedupe windows, two trigger types and two chances to double-
                # notify the moment both were enabled. Only one survives.
                #
                # What this worker is FOR now: it is the demand-driven supply
                # feed. It searches marketplaces for items people actually watch
                # and writes the comps to market_hits \u2014 which is the table the
                # snipe reads. That matters most for mtg/pokemon/yugioh, which
                # `marketplace_scrape_scheduler.SKIP_CATEGORIES` excludes and
                # which therefore had 0 buyable listings out of 609k rows
                # (measured 2026-08-06). Demand-scoping is what keeps the
                # outbound volume bounded: watched items are tens, the TCG
                # catalog is 80k+.
                scanned += 1

            except Exception as e:
                per_item_failures += 1
                # 2026-04-24: capture last per-item error for worker_runs.metadata
                # so the loud-but-empty pattern is finally surfaced.
                last_item_err = f"{type(e).__name__}: {e!s}"[:500]
                logger.warning(
                    "Failed to scan watchlist item %s: %s", str(wl_id), e,
                    exc_info=True,
                )

        logger.info(
            "Watchlist monitor cycle complete: scanned=%d failures=%d",
            scanned, per_item_failures,
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
        record_run(
            "watchlist_monitor_worker",
            cycle_status if "cycle_status" in locals() else "error",
            error_repr=last_item_err if "last_item_err" in locals() else None,
        )


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run(
            "watchlist_monitor_worker", "error",
            error_repr=f"{type(e).__name__}: {e!s}"[:500],
        )
        log_dead_letter("watchlist_monitor_worker", {}, e)
        logger.exception("watchlist_monitor_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
