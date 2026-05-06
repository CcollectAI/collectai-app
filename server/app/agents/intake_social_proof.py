"""
Social proof aggregation for QuickScan results.

Queries demand signals, trending data, recent sold items, and supply
snapshots to provide market context alongside item identification.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Categories where Discogs asking-price (is_listing=true) data is ingested.
# For these we surface a separate "list price" section alongside sold comps
# so users can see current-market asking prices distinctly from transactions.
LISTING_PRICE_CATEGORIES = {
    "vinyl_records",
    "anime_ost_vinyl",
    "anime_soundtrack",
    "anime_bluray",
    "city_pop_vinyl",
}


async def get_social_proof(
    category: Optional[str],
    item_key: Optional[str],
    pool,
) -> dict[str, Any]:
    """
    Aggregate social proof data for a scanned item.

    Returns:
        {
            "collector_count": int,
            "is_trending": bool,
            "trend_rank": int | None,
            "recent_sold": [{"title", "price", "currency", "sold_at", "source"}],
            "scarcity": {"listing_count", "supply_trend", "scarcity_score"}
        }
    """
    result: dict[str, Any] = {
        "collector_count": 0,
        "is_trending": False,
        "trend_rank": None,
        "recent_sold": [],
        "recent_listings": [],
        "scarcity": {
            "listing_count": 0,
            "supply_trend": "stable",
            "scarcity_score": 0.0,
        },
    }

    if not pool or not category:
        return result

    try:
        async with pool.acquire() as conn:
            # Collector count from demand_signals
            try:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(DISTINCT user_id)
                    FROM demand_signals
                    WHERE category = $1
                      AND item_key ILIKE $2
                    """,
                    category,
                    f"%{(item_key or '')[:60]}%",
                )
                result["collector_count"] = count or 0
            except Exception as e:
                logger.debug("Social proof collector count error: %s", e)

            # Trending from mv_demand_heat (materialized view).
            # Real columns are signal_count + unique_users (no rank /
            # heat_score). Use signal_count as the "heat" proxy and
            # rank by row_number() over the partition.
            try:
                row = await conn.fetchrow(
                    """
                    WITH ranked AS (
                      SELECT category, item_key,
                             ROW_NUMBER() OVER (PARTITION BY category ORDER BY signal_count DESC NULLS LAST) AS rank,
                             signal_count AS heat_score
                      FROM mv_demand_heat
                      WHERE category = $1
                    )
                    SELECT rank, heat_score
                    FROM ranked
                    WHERE item_key ILIKE $2
                    LIMIT 1
                    """,
                    category,
                    f"%{(item_key or '')[:60]}%",
                )
                if row:
                    result["is_trending"] = True
                    result["trend_rank"] = row["rank"]
            except Exception as e:
                logger.debug("Social proof trending error: %s", e)

            # Recent sold from market_hits (last 5)
            try:
                rows = await conn.fetch(
                    """
                    SELECT title, price, currency, ended_at, source
                    FROM market_hits
                    WHERE normalized_key ILIKE $1
                      AND price IS NOT NULL
                      AND price > 0
                      AND (is_listing IS NOT TRUE)
                      -- Partition prune: social proof shows recent sold;
                      -- 180d covers the window where prices are still
                      -- relevant. Without this filter every intake call
                      -- walks all monthly partitions of market_hits.
                      AND seen_at > now() - interval '180 days'
                    ORDER BY ended_at DESC NULLS LAST
                    LIMIT 5
                    """,
                    f"%{(item_key or '')[:60]}%",
                )
                result["recent_sold"] = [
                    {
                        "title": r["title"],
                        "price": float(r["price"]),
                        "currency": r["currency"] or "EUR",
                        "sold_at": r["ended_at"].isoformat() if r["ended_at"] else None,
                        "source": r["source"],
                    }
                    for r in rows
                ]
            except Exception as e:
                logger.debug("Social proof recent sold error: %s", e)

            # Recent listings (asking prices) — only for categories where
            # Discogs listing-price data is ingested. Uses price_eur (FX-
            # normalized) so UI doesn't mix currencies.
            if category in LISTING_PRICE_CATEGORIES:
                try:
                    rows = await conn.fetch(
                        """
                        SELECT title, price, currency, seen_at, source, url
                        FROM market_hits
                        WHERE normalized_key ILIKE $1
                          AND price IS NOT NULL
                          AND price > 0
                          AND is_listing IS TRUE
                        ORDER BY seen_at DESC NULLS LAST
                        LIMIT 5
                        """,
                        f"%{(item_key or '')[:60]}%",
                    )
                    result["recent_listings"] = [
                        {
                            "title": r["title"],
                            "price": float(r["price"]),
                            "currency": r["currency"] or "USD",
                            "seen_at": r["seen_at"].isoformat() if r["seen_at"] else None,
                            "source": r["source"],
                            "url": r["url"],
                        }
                        for r in rows
                    ]
                except Exception as e:
                    logger.debug("Social proof recent listings error: %s", e)

            # Scarcity from supply_snapshots. Real columns: listing_count
            # + avg/min/max_price_eur + snapshot_at. supply_trend and
            # scarcity_score are derived: trend = compare today's
            # listing_count to 7-day-prior; score = 1 - (count/30).
            try:
                row = await conn.fetchrow(
                    """
                    SELECT listing_count,
                           CASE
                             WHEN listing_count < 5 THEN 'tight'
                             WHEN listing_count < 15 THEN 'normal'
                             ELSE 'abundant'
                           END AS supply_trend,
                           GREATEST(0.0, 1.0 - (listing_count / 30.0))::float AS scarcity_score
                    FROM supply_snapshots
                    WHERE category = $1
                      AND item_key ILIKE $2
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """,
                    category,
                    f"%{(item_key or '')[:60]}%",
                )
                if row:
                    result["scarcity"] = {
                        "listing_count": row["listing_count"] or 0,
                        "supply_trend": row["supply_trend"] or "stable",
                        "scarcity_score": round(float(row["scarcity_score"] or 0), 2),
                    }
            except Exception as e:
                logger.debug("Social proof scarcity error: %s", e)

    except Exception as e:
        logger.warning("Social proof aggregation error: %s", e)

    return result
