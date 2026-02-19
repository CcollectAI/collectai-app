"""
Data moat helpers — supply tracking + demand signal recording.

These functions are called from various routers to build proprietary data
that strengthens model accuracy over time.

Supply snapshots:  Record listing counts per item/category after each crawl.
Demand signals:    Record user intent signals (searches, mandates, views).
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def _to_uuid_or_none(s: str | None) -> UUID | None:
    """Convert string to UUID, returning None if invalid."""
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, AttributeError):
        return None


def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except (ImportError, RuntimeError, OSError):
        return None


async def record_supply_snapshot(
    category: str,
    item_key: str,
    listing_count: int,
    avg_price_eur: Optional[float] = None,
    min_price_eur: Optional[float] = None,
    max_price_eur: Optional[float] = None,
    source: str = "firecrawl",
    metadata: Optional[dict] = None,
) -> bool:
    """
    Record a supply snapshot after crawling listings for an item.

    Called from deal_discovery_agent after each marketplace search.

    Returns True if recorded, False on failure.
    """
    pool = _get_db_pool()
    if pool is None:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.supply_snapshots
                    (category, item_key, source, listing_count,
                     avg_price_eur, min_price_eur, max_price_eur, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                """,
                category,
                item_key,
                source,
                listing_count,
                avg_price_eur,
                min_price_eur,
                max_price_eur,
                json.dumps(metadata or {}),
            )
        return True
    except Exception as e:
        logger.warning("[data_moat] Failed to record supply snapshot: %s", e)
        return False


async def record_demand_signal(
    signal_type: str,
    category: Optional[str] = None,
    item_key: Optional[str] = None,
    query_text: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    """
    Record a demand signal from a user action.

    Signal types:
    - mandate_created: User created a purchase mandate for an item
    - search_query:    User searched for items/categories
    - item_viewed:     User viewed item detail page
    - price_alert_set: User set a price alert
    - watchlist_add:   User added item to watchlist

    Called from mandate_router, search endpoints, item detail, etc.

    Returns True if recorded, False on failure.
    """
    pool = _get_db_pool()
    if pool is None:
        return False

    valid_types = {
        "mandate_created", "search_query", "item_viewed",
        "price_alert_set", "watchlist_add",
    }
    if signal_type not in valid_types:
        logger.warning("[data_moat] Invalid signal type: %s", signal_type)
        return False

    try:
        uid = _to_uuid_or_none(user_id)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.demand_signals
                    (signal_type, category, item_key, query_text, user_id)
                VALUES ($1, $2, $3, $4, $5)
                """,
                signal_type,
                category,
                item_key,
                query_text,
                uid,
            )
        return True
    except Exception as e:
        logger.warning("[data_moat] Failed to record demand signal: %s", e)
        return False


async def get_supply_trend(
    category: str,
    item_key: str,
    days: int = 30,
) -> list[dict]:
    """
    Get supply trend for an item over the last N days.

    Returns list of {snap_date, avg_listings, avg_price} dicts.
    """
    pool = _get_db_pool()
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT snap_date, avg_listings, avg_price
                FROM public.mv_supply_trend
                WHERE category = $1 AND item_key = $2
                  AND snap_date >= current_date - $3::int
                ORDER BY snap_date ASC
                """,
                category,
                item_key,
                days,
            )
        return [
            {
                "snap_date": str(row["snap_date"]),
                "avg_listings": row["avg_listings"],
                "avg_price": float(row["avg_price"]) if row["avg_price"] else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning("[data_moat] Failed to get supply trend: %s", e)
        return []


async def get_demand_heat(
    category: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Get top trending items by demand signal volume.

    Returns list of {category, item_key, signal_type, signal_count, unique_users}.
    """
    pool = _get_db_pool()
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            if category:
                rows = await conn.fetch(
                    """
                    SELECT category, item_key, signal_type,
                           signal_count, unique_users, last_signal_at
                    FROM public.mv_demand_heat
                    WHERE category = $1
                    ORDER BY signal_count DESC
                    LIMIT $2
                    """,
                    category,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT category, item_key, signal_type,
                           signal_count, unique_users, last_signal_at
                    FROM public.mv_demand_heat
                    ORDER BY signal_count DESC
                    LIMIT $1
                    """,
                    limit,
                )
        return [
            {
                "category": row["category"],
                "item_key": row["item_key"],
                "signal_type": row["signal_type"],
                "signal_count": row["signal_count"],
                "unique_users": row["unique_users"],
                "last_signal_at": row["last_signal_at"].isoformat() if row["last_signal_at"] else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning("[data_moat] Failed to get demand heat: %s", e)
        return []
