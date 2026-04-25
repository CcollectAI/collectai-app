from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response
from app.rate_limit import per_user_rate_limit
from app.cache import cache_get, cache_set
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode

router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = logging.getLogger(__name__)

# Per-user: 30 analytics requests per minute
_analytics_limit = per_user_rate_limit(30, window_seconds=60, scope="analytics")

_DEEPDIVE_CACHE_TTL = 21600  # 6 hours


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
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """
    Collection trend graph:
    - total value over time  (from price_predictions for user's items)
    - per-category gain/loss (earliest vs latest predicted value)
    """
    limit, offset = pagination

    pool = get_db_pool()
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
                    date_trunc('day', pp.generated_at) AS day,
                    SUM(pp.q50)                AS total_value
                FROM price_predictions pp
                JOIN items i ON i.canonical_key = pp.item_ref
                WHERE i.user_id = $1
                  AND pp.generated_at >= $2
                GROUP BY date_trunc('day', pp.generated_at)
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
                        i.id AS item_id,
                        i.category,
                        pp.q50 AS first_value
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_key = pp.item_ref
                    WHERE i.user_id = $1 AND pp.generated_at >= $2
                    ORDER BY i.id, pp.generated_at ASC
                ),
                latest AS (
                    SELECT DISTINCT ON (i.id)
                        i.id AS item_id,
                        i.category,
                        pp.q50 AS last_value
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_key = pp.item_ref
                    WHERE i.user_id = $1 AND pp.generated_at >= $2
                    ORDER BY i.id, pp.generated_at DESC
                )
                SELECT
                    e.category,
                    SUM(e.first_value) AS sum_first,
                    SUM(l.last_value)  AS sum_last
                FROM earliest e
                JOIN latest l ON l.item_id = e.item_id
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

            # ------- DCA cost basis history -------
            # Compute cumulative cost basis over time from items with purchase_price
            dca_history = None
            try:
                dca_rows = await conn.fetch(
                    """
                    WITH daily AS (
                        SELECT
                            date_trunc('day', COALESCE(i.purchased_at, i.created_at)) AS day,
                            SUM(i.purchase_price) AS day_cost
                        FROM items i
                        WHERE i.user_id = $1
                          AND i.purchase_price IS NOT NULL
                          AND COALESCE(i.purchased_at, i.created_at) >= $2
                        GROUP BY 1
                    )
                    SELECT day, SUM(day_cost) OVER (ORDER BY day) AS cumulative_cost
                    FROM daily
                    ORDER BY day
                    """,
                    user_id,
                    cutoff,
                )
                if dca_rows:
                    dca_history = [
                        TimeseriesPoint(ts=row["day"], value=float(row["cumulative_cost"] or 0))
                        for row in dca_rows
                    ]
            except Exception as e:
                logger.debug("[collection/trends] DCA query failed (column may not exist): %s", e)

            return CollectionTrendResponse(
                currency=currency,
                total_history=total_history[offset:offset + limit],
                dca_history=dca_history,
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
    pagination: tuple[int, int] = Depends(pagination_params),
    user_id: str = Depends(get_current_user_id),
):
    try:
        UUID(item_id)
    except ValueError:
        raise error_response(400, "Invalid item_id format", code=ErrorCode.VALIDATION_ERROR)
    """
    Item-level trend for detail screen:
    - historical predicted value  (q50 from price_predictions)
    - model confidence over time  (conf_score from price_predictions)
    """
    limit, offset = pagination

    pool = get_db_pool()
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
                history=history[offset:offset + limit],
                model_confidence=confidence[offset:offset + limit] if confidence else None,
            )

    except Exception as e:
        logger.error(f"[items/{item_id}/trends] DB error: {e}")
        return ItemTrendResponse(
            item_id=item_id,
            currency=currency,
            history=[],
            model_confidence=None,
        )


class CategoryBreakdownItem(BaseModel):
    category: str
    item_count: int
    total_value: float
    pct_of_portfolio: float
    gain_pct: float


class PortfolioCategoryBreakdownResponse(BaseModel):
    breakdown: List[CategoryBreakdownItem]
    total_value: float


@router.get("/portfolio/category-breakdown", response_model=PortfolioCategoryBreakdownResponse)
async def get_portfolio_category_breakdown(
    user_id: str = Depends(get_current_user_id),
):
    """
    Portfolio value broken down by category.
    Uses latest q50 price prediction per item.
    """
    # Check cache (user-specific)
    cache_key = f"portfolio_breakdown:{user_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    pool = get_db_pool()
    if not pool:
        return PortfolioCategoryBreakdownResponse(breakdown=[], total_value=0.0)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH latest_pred AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref,
                        pp.q50,
                        pp.generated_at
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_key = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at DESC
                ),
                earliest_pred AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref,
                        pp.q50 AS first_q50
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_key = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at ASC
                )
                SELECT
                    i.category,
                    COUNT(*) AS item_count,
                    COALESCE(SUM(lp.q50), 0) AS total_value,
                    COALESCE(SUM(ep.first_q50), 0) AS first_total
                FROM items i
                LEFT JOIN latest_pred lp ON lp.item_ref = i.canonical_key
                LEFT JOIN earliest_pred ep ON ep.item_ref = i.canonical_key
                WHERE i.user_id = $1
                  AND i.category IS NOT NULL
                GROUP BY i.category
                ORDER BY total_value DESC
                """,
                user_id,
            )

            total_value = sum(float(r["total_value"] or 0) for r in rows)
            breakdown = []
            for r in rows:
                val = float(r["total_value"] or 0)
                first = float(r["first_total"] or 0)
                gain_pct = ((val - first) / first) if first > 0 else 0.0
                breakdown.append(CategoryBreakdownItem(
                    category=r["category"],
                    item_count=r["item_count"],
                    total_value=round(val, 2),
                    pct_of_portfolio=round(val / total_value, 4) if total_value > 0 else 0.0,
                    gain_pct=round(gain_pct, 4),
                ))

            result = PortfolioCategoryBreakdownResponse(
                breakdown=breakdown,
                total_value=round(total_value, 2),
            )
            cache_set(cache_key, result, ttl=_DEEPDIVE_CACHE_TTL)
            return result

    except Exception as e:
        logger.error(f"[portfolio/category-breakdown] DB error: {e}")
        return PortfolioCategoryBreakdownResponse(breakdown=[], total_value=0.0)


@router.get("/categories/{category}/deep-dive", response_model=CategoryDeepDiveResponse)
async def get_category_deep_dive(
    category: str,
    days: int = Query(30, ge=7, le=365),
    currency: str = Query("EUR"),
    pagination: tuple[int, int] = Depends(pagination_params),
    _rl: None = Depends(_analytics_limit),
    user_id: str = Depends(get_current_user_id),
):
    """
    Category deep dive:
    - avg market price          (from market_hits)
    - value distribution        (daily avg price series)
    - volume trends             (daily listing count)
    - most-traded items         (normalized_key with highest listing count)
    - top movers                (biggest price delta over the period)
    """
    limit, offset = pagination

    # Check cache
    cache_key = f"deepdive:{category}:{days}:{currency}:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    pool = get_db_pool()
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
            # ------- combined daily stats: avg price, volume, and overall avg -------
            # Single scan of market_hits instead of 3 separate queries.
            daily_rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', created_at)                    AS day,
                    AVG(price) FILTER (WHERE price IS NOT NULL)      AS avg_price,
                    COUNT(*)                                         AS cnt,
                    SUM(COUNT(*)) OVER ()                            AS grand_count,
                    SUM(SUM(CASE WHEN price IS NOT NULL THEN price ELSE 0 END)) OVER ()
                        / NULLIF(SUM(COUNT(price)) OVER (), 0)      AS overall_avg
                FROM market_hits
                WHERE normalized_key LIKE $1 || '%'
                  AND created_at >= $2
                  AND (is_listing IS NOT TRUE)
                GROUP BY date_trunc('day', created_at)
                ORDER BY day
                """,
                category.lower(),
                cutoff,
            )

            avg_market_price = float(daily_rows[0]["overall_avg"] or 0) if daily_rows else 0.0
            value_distribution = [
                TimeseriesPoint(ts=row["day"], value=float(row["avg_price"] or 0))
                for row in daily_rows
            ]
            volume_trend = [
                TimeseriesPoint(ts=row["day"], value=float(row["cnt"]))
                for row in daily_rows
            ]

            # ------- top traded + top movers in a single query -------
            # Uses one CTE scan to compute both rankings.
            combo_rows = await conn.fetch(
                """
                WITH per_key AS (
                    SELECT
                        normalized_key,
                        COALESCE(MAX(title), normalized_key) AS name,
                        COUNT(*)                             AS trades,
                        (ARRAY_AGG(price ORDER BY created_at ASC)  FILTER (WHERE price IS NOT NULL))[1]  AS first_price,
                        (ARRAY_AGG(price ORDER BY created_at DESC) FILTER (WHERE price IS NOT NULL))[1] AS last_price,
                        COUNT(price)                         AS price_cnt
                    FROM market_hits
                    WHERE normalized_key LIKE $1 || '%'
                      AND created_at >= $2
                      AND (is_listing IS NOT TRUE)
                    GROUP BY normalized_key
                ),
                ranked AS (
                    SELECT
                        normalized_key, name, trades, first_price, last_price, price_cnt,
                        CASE WHEN first_price > 0 AND price_cnt >= 2
                             THEN (last_price - first_price) / first_price
                             ELSE 0
                        END AS change_pct,
                        ROW_NUMBER() OVER (ORDER BY trades DESC)                                                                        AS trade_rank,
                        ROW_NUMBER() OVER (ORDER BY ABS(CASE WHEN first_price > 0 AND price_cnt >= 2
                                                             THEN (last_price - first_price) / first_price
                                                             ELSE 0 END) DESC)                                                          AS mover_rank
                    FROM per_key
                )
                SELECT normalized_key, name, trades, first_price, last_price,
                       price_cnt, change_pct, trade_rank, mover_rank
                FROM ranked
                WHERE trade_rank <= 10 OR mover_rank <= 10
                """,
                category.lower(),
                cutoff,
            )

            top_traded_items = sorted(
                [
                    {
                        "item_id": row["normalized_key"],
                        "name": row["name"],
                        "trades": row["trades"],
                    }
                    for row in combo_rows
                    if row["trade_rank"] <= 10
                ],
                key=lambda x: x["trades"],
                reverse=True,
            )
            top_movers = sorted(
                [
                    {
                        "item_id": row["normalized_key"],
                        "name": row["name"],
                        "change_pct": round(float(row["change_pct"] or 0), 4),
                    }
                    for row in combo_rows
                    if row["mover_rank"] <= 10
                ],
                key=lambda x: abs(x["change_pct"]),
                reverse=True,
            )

            # Record demand signal with geo enrichment (best-effort)
            try:
                from app.features.data_moat import record_demand_signal, get_user_geo
                region, country = await get_user_geo(user_id)
                await record_demand_signal(
                    signal_type="category_viewed",
                    category=category,
                    user_id=user_id,
                    region=region,
                    country_code=country,
                )
            except Exception as e:
                logger.debug("Demand signal recording failed (best-effort): %s", e)

            result = CategoryDeepDiveResponse(
                category=category,
                currency=currency,
                avg_market_price=round(avg_market_price, 2),
                value_distribution=value_distribution[offset:offset + limit],
                volume_trend=volume_trend[offset:offset + limit],
                top_traded_items=top_traded_items[offset:offset + limit],
                top_movers=top_movers[offset:offset + limit],
            )
            cache_set(cache_key, result, ttl=_DEEPDIVE_CACHE_TTL)
            return result

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
