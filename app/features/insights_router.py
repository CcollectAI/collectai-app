from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.auth import get_current_user_id

router = APIRouter(prefix="/insights", tags=["insights"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except (ImportError, RuntimeError, OSError) as e:
        logger.debug(f"DB pool not available: {e}")
        return None


# ---------------------------------------------------------------------------
# Thresholds for insight generation
# ---------------------------------------------------------------------------

_OVEREXPOSURE_THRESHOLD = 0.40   # category > 40% of portfolio -> flagged
_HIGH_RISK_THRESHOLD = 0.50      # category > 50% -> "high" risk


# ---------------------------------------------------------------------------
# Response models (unchanged)
# ---------------------------------------------------------------------------

class CategoryExposure(BaseModel):
    category: str
    share_pct: float
    risk_level: str = Field(..., description="low | medium | high")


class RareSetAlert(BaseModel):
    category: str
    item_name: str
    note: str


class TrendingItem(BaseModel):
    category: str
    item_name: str
    change_pct: float


class PersonalizedInsightsResponse(BaseModel):
    overexposed_categories: List[CategoryExposure]
    diversification_suggestions: List[str]
    rare_set_alerts: List[RareSetAlert]
    trending_items: List[TrendingItem]


class HomeWidgetResponse(BaseModel):
    collection_value: float
    today_change: float
    biggest_mover_name: str
    biggest_mover_change: float
    currency: str = "EUR"
    quickscan_shortcut: str = Field(
        "/quickscan-advanced/single", description="Relative path for one-tap scan"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/personalized", response_model=PersonalizedInsightsResponse)
async def get_personalized_insights(user_id: str = Depends(get_current_user_id)) -> PersonalizedInsightsResponse:
    """
    Personalized insights based on the user's actual portfolio composition:
    - Over-exposed categories (concentration risk)
    - Diversification suggestions
    - Rare-set / retirement alerts   (TODO: needs catalogue metadata)
    - Trending items from market data
    """
    pool = _get_db_pool()
    if not pool:
        return PersonalizedInsightsResponse(
            overexposed_categories=[],
            diversification_suggestions=[],
            rare_set_alerts=[],
            trending_items=[],
        )

    try:
        async with pool.acquire() as conn:
            # ---- Category exposure from user's items ----
            cat_rows = await conn.fetch(
                """
                SELECT
                    category,
                    COUNT(*)::float AS cnt,
                    SUM(COUNT(*)) OVER ()::float AS total
                FROM items
                WHERE user_id = $1
                GROUP BY category
                ORDER BY cnt DESC
                """,
                user_id,
            )

            overexposed: List[CategoryExposure] = []
            category_shares: dict[str, float] = {}
            for row in cat_rows:
                share = row["cnt"] / row["total"] if row["total"] else 0.0
                category_shares[row["category"]] = share
                if share >= _OVEREXPOSURE_THRESHOLD:
                    if share >= _HIGH_RISK_THRESHOLD:
                        risk = "high"
                    else:
                        risk = "medium"
                    overexposed.append(
                        CategoryExposure(
                            category=row["category"],
                            share_pct=round(share, 4),
                            risk_level=risk,
                        )
                    )

            # ---- Diversification suggestions ----
            suggestions: List[str] = []
            if len(category_shares) == 1:
                only_cat = list(category_shares.keys())[0]
                suggestions.append(
                    f"Your entire portfolio is in '{only_cat}'. "
                    "Consider diversifying into other categories to reduce risk."
                )
            elif overexposed:
                top_cat = overexposed[0].category
                suggestions.append(
                    f"Your '{top_cat}' exposure is {overexposed[0].share_pct:.0%} of "
                    "your portfolio. Adding items from other categories would reduce "
                    "concentration risk."
                )
            if len(category_shares) >= 2:
                sorted_cats = sorted(category_shares.items(), key=lambda x: x[1])
                smallest_cat = sorted_cats[0][0]
                suggestions.append(
                    f"Consider growing your '{smallest_cat}' collection -- it is "
                    "currently your smallest category."
                )

            # ---- Trending items from market_hits (positive price delta, last 14 days) ----
            cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            trend_rows = await conn.fetch(
                """
                WITH first_last AS (
                    SELECT
                        normalized_key,
                        COALESCE(MAX(title), normalized_key) AS item_name,
                        (ARRAY_AGG(price ORDER BY created_at ASC))[1]  AS first_price,
                        (ARRAY_AGG(price ORDER BY created_at DESC))[1] AS last_price
                    FROM market_hits
                    WHERE created_at >= $1
                      AND price IS NOT NULL
                    GROUP BY normalized_key
                    HAVING COUNT(*) >= 2
                )
                SELECT
                    normalized_key,
                    item_name,
                    first_price,
                    last_price,
                    CASE WHEN first_price > 0
                         THEN (last_price - first_price) / first_price
                         ELSE 0
                    END AS change_pct
                FROM first_last
                WHERE last_price > first_price
                ORDER BY change_pct DESC
                LIMIT 5
                """,
                cutoff,
            )
            trending = [
                TrendingItem(
                    category=_extract_category_from_key(row["normalized_key"]),
                    item_name=row["item_name"] or row["normalized_key"],
                    change_pct=round(float(row["change_pct"] or 0), 4),
                )
                for row in trend_rows
            ]

            # ---- Rare-set alerts ----
            # TODO: requires catalogue / retirement metadata; return empty for now
            rare_alerts: List[RareSetAlert] = []

            return PersonalizedInsightsResponse(
                overexposed_categories=overexposed,
                diversification_suggestions=suggestions,
                rare_set_alerts=rare_alerts,
                trending_items=trending,
            )

    except asyncpg.PostgresError as e:
        logger.error(f"[insights/personalized] DB error: {e}")
        return PersonalizedInsightsResponse(
            overexposed_categories=[],
            diversification_suggestions=[],
            rare_set_alerts=[],
            trending_items=[],
        )


@router.get("/home-widget", response_model=HomeWidgetResponse)
async def get_home_widget(user_id: str = Depends(get_current_user_id)) -> HomeWidgetResponse:
    """
    'What's it worth today?' home widget snapshot.
    Computes real collection value and daily change from price_predictions.
    """
    pool = _get_db_pool()
    if not pool:
        return HomeWidgetResponse(
            collection_value=0.0,
            today_change=0.0,
            biggest_mover_name="--",
            biggest_mover_change=0.0,
            currency="EUR",
        )

    try:
        async with pool.acquire() as conn:
            # Latest predicted value for each item -> total collection value
            value_row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pp.q50), 0) AS total_value
                FROM (
                    SELECT DISTINCT ON (pp.item_id) pp.q50
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                    ORDER BY pp.item_id, pp.asof DESC
                ) pp
                """,
                user_id,
            )
            collection_value = float(value_row["total_value"]) if value_row else 0.0

            # Yesterday's total for change calculation
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            yesterday_row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pp.q50), 0) AS total_value
                FROM (
                    SELECT DISTINCT ON (pp.item_id) pp.q50
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                      AND pp.asof <= $2
                    ORDER BY pp.item_id, pp.asof DESC
                ) pp
                """,
                user_id,
                yesterday,
            )
            yesterday_value = float(yesterday_row["total_value"]) if yesterday_row else 0.0
            today_change = collection_value - yesterday_value

            # Biggest mover: item with largest absolute q50 change today vs yesterday
            mover_row = await conn.fetchrow(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id,
                        pp.q50 AS latest_q50
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                    ORDER BY pp.item_id, pp.asof DESC
                ),
                prev AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id,
                        pp.q50 AS prev_q50
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                      AND pp.asof <= $2
                    ORDER BY pp.item_id, pp.asof DESC
                )
                SELECT
                    COALESCE(i.title, i.normalized_key, i.id::text) AS item_name,
                    (l.latest_q50 - COALESCE(p.prev_q50, l.latest_q50)) AS change
                FROM latest l
                JOIN items i ON i.id = l.item_id
                LEFT JOIN prev p ON p.item_id = l.item_id
                ORDER BY ABS(l.latest_q50 - COALESCE(p.prev_q50, l.latest_q50)) DESC
                LIMIT 1
                """,
                user_id,
                yesterday,
            )
            biggest_name = mover_row["item_name"] if mover_row else "--"
            biggest_change = float(mover_row["change"]) if mover_row else 0.0

            return HomeWidgetResponse(
                collection_value=round(collection_value, 2),
                today_change=round(today_change, 2),
                biggest_mover_name=biggest_name,
                biggest_mover_change=round(biggest_change, 2),
                currency="EUR",
            )

    except asyncpg.PostgresError as e:
        logger.error(f"[insights/home-widget] DB error: {e}")
        return HomeWidgetResponse(
            collection_value=0.0,
            today_change=0.0,
            biggest_mover_name="--",
            biggest_mover_change=0.0,
            currency="EUR",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_category_from_key(normalized_key: str) -> str:
    """
    normalized_key is typically formatted as 'category|...' (e.g. 'lego|10297|...').
    Extract the leading category segment.
    """
    if normalized_key and "|" in normalized_key:
        return normalized_key.split("|", 1)[0]
    return normalized_key or "unknown"
