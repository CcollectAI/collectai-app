from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug(f"DB pool not available: {e}")
        return None


# ---------------------------------------------------------------------------
# Response models (unchanged)
# ---------------------------------------------------------------------------

class TimeseriesPoint(BaseModel):
    ts: datetime
    value: float


class ItemTrendResponse(BaseModel):
    item_id: str
    currency: str = "EUR"
    history: List[TimeseriesPoint]
    model_confidence: Optional[List[TimeseriesPoint]] = None


class CollectionTrendResponse(BaseModel):
    currency: str = "EUR"
    total_history: List[TimeseriesPoint]
    dca_history: Optional[List[TimeseriesPoint]] = None
    per_category_gain_loss: dict = Field(default_factory=dict)


class CategoryDeepDiveResponse(BaseModel):
    category: str
    currency: str = "EUR"
    avg_market_price: float
    value_distribution: List[TimeseriesPoint]
    volume_trend: List[TimeseriesPoint]
    top_traded_items: List[dict]
    top_movers: List[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/collection/trends", response_model=CollectionTrendResponse)
async def get_collection_trends(
    days: int = Query(30, ge=1, le=365),
    currency: str = Query("EUR"),
    user_id: str = Depends(get_current_user_id),
):
    """
    Collection trend graph:
    - total value over time  (from price_predictions for user's items)
    - per-category gain/loss (earliest vs latest predicted value)
    """
    pool = _get_db_pool()
    if not pool:
        return CollectionTrendResponse(
            currency=currency,
            total_history=[],
            dca_history=None,
            per_category_gain_loss={},
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with pool.acquire() as conn:
            # ------- total portfolio value over time -------
            # For each day, sum the latest predicted q50 for every item
            # owned by this user that had a prediction on or before that day.
            ts_rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', pp.asof) AS day,
                    SUM(pp.q50)                AS total_value
                FROM price_predictions pp
                JOIN items i ON i.id = pp.item_id
                WHERE i.user_id = $1
                  AND pp.asof >= $2
                GROUP BY date_trunc('day', pp.asof)
                ORDER BY day
                """,
                user_id,
                cutoff,
            )
            total_history = [
                TimeseriesPoint(ts=row["day"], value=float(row["total_value"] or 0))
                for row in ts_rows
            ]

            # ------- per-category gain/loss -------
            cat_rows = await conn.fetch(
                """
                WITH earliest AS (
                    SELECT DISTINCT ON (i.id)
                        i.category,
                        pp.q50 AS first_value
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1 AND pp.asof >= $2
                    ORDER BY i.id, pp.asof ASC
                ),
                latest AS (
                    SELECT DISTINCT ON (i.id)
                        i.category,
                        pp.q50 AS last_value
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1 AND pp.asof >= $2
                    ORDER BY i.id, pp.asof DESC
                )
                SELECT
                    e.category,
                    SUM(e.first_value) AS sum_first,
                    SUM(l.last_value)  AS sum_last
                FROM earliest e
                JOIN latest l USING (category)
                GROUP BY e.category
                """,
                user_id,
                cutoff,
            )
            per_category: dict = {}
            for row in cat_rows:
                first_val = float(row["sum_first"] or 0)
                last_val = float(row["sum_last"] or 0)
                gain_pct = ((last_val - first_val) / first_val) if first_val else 0.0
                per_category[row["category"]] = {"gain_pct": round(gain_pct, 4)}

            return CollectionTrendResponse(
                currency=currency,
                total_history=total_history,
                dca_history=None,  # TODO: track DCA cost basis
                per_category_gain_loss=per_category,
            )

    except Exception as e:
        logger.error(f"[collection/trends] DB error: {e}")
        return CollectionTrendResponse(
            currency=currency,
            total_history=[],
            dca_history=None,
            per_category_gain_loss={},
        )


@router.get("/items/{item_id}/trends", response_model=ItemTrendResponse)
async def get_item_trends(
    item_id: str,
    days: int = Query(30, ge=1, le=365),
    currency: str = Query("EUR"),
):
    """
    Item-level trend for detail screen:
    - historical predicted value  (q50 from price_predictions)
    - model confidence over time  (conf_score from price_predictions)
    """
    pool = _get_db_pool()
    if not pool:
        return ItemTrendResponse(
            item_id=item_id,
            currency=currency,
            history=[],
            model_confidence=[],
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT asof, q50, conf_score
                FROM price_predictions
                WHERE item_id = $1
                  AND asof >= $2
                ORDER BY asof
                """,
                item_id,
                cutoff,
            )

            history = [
                TimeseriesPoint(ts=row["asof"], value=float(row["q50"] or 0))
                for row in rows
            ]
            confidence = [
                TimeseriesPoint(ts=row["asof"], value=float(row["conf_score"] or 0))
                for row in rows
                if row["conf_score"] is not None
            ]

            return ItemTrendResponse(
                item_id=item_id,
                currency=currency,
                history=history,
                model_confidence=confidence or None,
            )

    except Exception as e:
        logger.error(f"[items/{item_id}/trends] DB error: {e}")
        return ItemTrendResponse(
            item_id=item_id,
            currency=currency,
            history=[],
            model_confidence=None,
        )


@router.get("/categories/{category}/deep-dive", response_model=CategoryDeepDiveResponse)
async def get_category_deep_dive(
    category: str,
    days: int = Query(30, ge=7, le=365),
    currency: str = Query("EUR"),
):
    """
    Category deep dive:
    - avg market price          (from market_hits)
    - value distribution        (daily avg price series)
    - volume trends             (daily listing count)
    - most-traded items         (normalized_key with highest listing count)
    - top movers                (biggest price delta over the period)
    """
    pool = _get_db_pool()
    if not pool:
        return CategoryDeepDiveResponse(
            category=category,
            currency=currency,
            avg_market_price=0.0,
            value_distribution=[],
            volume_trend=[],
            top_traded_items=[],
            top_movers=[],
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with pool.acquire() as conn:
            # ------- avg market price -------
            avg_row = await conn.fetchrow(
                """
                SELECT AVG(price) AS avg_price
                FROM market_hits
                WHERE normalized_key LIKE $1 || '%'
                  AND created_at >= $2
                  AND price IS NOT NULL
                """,
                category.lower(),
                cutoff,
            )
            avg_market_price = float(avg_row["avg_price"] or 0) if avg_row else 0.0

            # ------- value distribution (daily avg) -------
            val_rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', created_at) AS day,
                    AVG(price)                    AS avg_price
                FROM market_hits
                WHERE normalized_key LIKE $1 || '%'
                  AND created_at >= $2
                  AND price IS NOT NULL
                GROUP BY date_trunc('day', created_at)
                ORDER BY day
                """,
                category.lower(),
                cutoff,
            )
            value_distribution = [
                TimeseriesPoint(ts=row["day"], value=float(row["avg_price"] or 0))
                for row in val_rows
            ]

            # ------- volume trend (daily count) -------
            vol_rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', created_at) AS day,
                    COUNT(*)                      AS cnt
                FROM market_hits
                WHERE normalized_key LIKE $1 || '%'
                  AND created_at >= $2
                GROUP BY date_trunc('day', created_at)
                ORDER BY day
                """,
                category.lower(),
                cutoff,
            )
            volume_trend = [
                TimeseriesPoint(ts=row["day"], value=float(row["cnt"]))
                for row in vol_rows
            ]

            # ------- top traded items -------
            traded_rows = await conn.fetch(
                """
                SELECT
                    normalized_key,
                    COALESCE(MAX(title), normalized_key) AS name,
                    COUNT(*) AS trades
                FROM market_hits
                WHERE normalized_key LIKE $1 || '%'
                  AND created_at >= $2
                GROUP BY normalized_key
                ORDER BY trades DESC
                LIMIT 10
                """,
                category.lower(),
                cutoff,
            )
            top_traded_items = [
                {
                    "item_id": row["normalized_key"],
                    "name": row["name"],
                    "trades": row["trades"],
                }
                for row in traded_rows
            ]

            # ------- top movers (biggest price change) -------
            mover_rows = await conn.fetch(
                """
                WITH first_last AS (
                    SELECT
                        normalized_key,
                        COALESCE(MAX(title), normalized_key) AS name,
                        (ARRAY_AGG(price ORDER BY created_at ASC))[1]  AS first_price,
                        (ARRAY_AGG(price ORDER BY created_at DESC))[1] AS last_price
                    FROM market_hits
                    WHERE normalized_key LIKE $1 || '%'
                      AND created_at >= $2
                      AND price IS NOT NULL
                    GROUP BY normalized_key
                    HAVING COUNT(*) >= 2
                )
                SELECT
                    normalized_key,
                    name,
                    first_price,
                    last_price,
                    CASE WHEN first_price > 0
                         THEN (last_price - first_price) / first_price
                         ELSE 0
                    END AS change_pct
                FROM first_last
                ORDER BY ABS(change_pct) DESC
                LIMIT 10
                """,
                category.lower(),
                cutoff,
            )
            top_movers = [
                {
                    "item_id": row["normalized_key"],
                    "name": row["name"],
                    "change_pct": round(float(row["change_pct"] or 0), 4),
                }
                for row in mover_rows
            ]

            return CategoryDeepDiveResponse(
                category=category,
                currency=currency,
                avg_market_price=round(avg_market_price, 2),
                value_distribution=value_distribution,
                volume_trend=volume_trend,
                top_traded_items=top_traded_items,
                top_movers=top_movers,
            )

    except Exception as e:
        logger.error(f"[categories/{category}/deep-dive] DB error: {e}")
        return CategoryDeepDiveResponse(
            category=category,
            currency=currency,
            avg_market_price=0.0,
            value_distribution=[],
            volume_trend=[],
            top_traded_items=[],
            top_movers=[],
        )
