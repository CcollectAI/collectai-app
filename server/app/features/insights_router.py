from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.config import OVEREXPOSURE_THRESHOLD, HIGH_RISK_THRESHOLD
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/insights", tags=["Insights"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thresholds for insight generation
# ---------------------------------------------------------------------------

_OVEREXPOSURE_THRESHOLD = OVEREXPOSURE_THRESHOLD
_HIGH_RISK_THRESHOLD = HIGH_RISK_THRESHOLD


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
async def get_personalized_insights(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    _rl=Depends(per_user_rate_limit(20, window_seconds=60, scope="insights")),
) -> PersonalizedInsightsResponse:
    """
    Personalized insights based on the user's actual portfolio composition:
    - Over-exposed categories (concentration risk)
    - Diversification suggestions
    - Rare-set / retirement alerts   (requires catalogue metadata — see set_router)
    - Trending items from market data
    """
    limit, offset = pagination

    pool = get_db_pool()
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

            # ---- Rare-set alerts (near-complete sets) ----
            rare_alerts: List[RareSetAlert] = []
            try:
                import json as _json
                set_rows = await conn.fetch(
                    """
                    SELECT sr.id, sr.category_id, sr.set_name, sr.total_items, sr.items_json
                    FROM set_registry sr
                    WHERE sr.total_items > 0
                    """
                )
                for sr in set_rows:
                    total = sr["total_items"]
                    if total <= 0:
                        continue
                    # Parse items_json for set item keys
                    try:
                        items_list = sr["items_json"] if isinstance(sr["items_json"], list) else _json.loads(sr["items_json"] or "[]")
                    except Exception:
                        continue
                    set_keys = [it.get("key") or it.get("name", "") for it in items_list if isinstance(it, dict)]
                    if not set_keys:
                        continue

                    # Check user's owned items in this category
                    owned_rows = await conn.fetch(
                        """
                        SELECT normalized_key, title FROM items
                        WHERE user_id = $1 AND category = $2
                        """,
                        user_id, sr["category_id"],
                    )
                    if not owned_rows:
                        continue

                    # Match owned items against set keys
                    owned_count = 0
                    for sk in set_keys:
                        sk_lower = sk.lower()
                        for orow in owned_rows:
                            nk = orow["normalized_key"]
                            title = orow["title"]
                            if (nk and sk_lower in nk.lower()) or (title and sk_lower in title.lower()):
                                owned_count += 1
                                break

                    pct = owned_count / total
                    if 0.80 <= pct < 1.0:
                        missing = total - owned_count
                        rare_alerts.append(RareSetAlert(
                            category=sr["category_id"],
                            item_name=sr["set_name"],
                            note=f"You own {owned_count}/{total} ({pct:.0%}). Only {missing} item{'s' if missing != 1 else ''} to complete!",
                        ))
            except Exception as e:
                logger.debug("[insights] rare-set alert check failed: %s", e)

            return PersonalizedInsightsResponse(
                overexposed_categories=overexposed[offset:offset + limit],
                diversification_suggestions=suggestions[offset:offset + limit],
                rare_set_alerts=rare_alerts[offset:offset + limit],
                trending_items=trending[offset:offset + limit],
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
async def get_home_widget(
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(30, scope="insights")),
) -> HomeWidgetResponse:
    """
    'What's it worth today?' home widget snapshot.
    Computes real collection value and daily change from price_predictions.
    """
    pool = get_db_pool()
    if not pool:
        return HomeWidgetResponse(
            collection_value=0.0,
            today_change=0.0,
            biggest_mover_name="--",
            biggest_mover_change=0.0,
            currency="EUR",
        )

    try:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)

        async with pool.acquire() as conn:
            # Single combined query: current total, yesterday total, and biggest mover.
            # Uses two CTEs (latest + prev) that are referenced once for all three metrics,
            # replacing the previous 3 separate round-trips.
            row = await conn.fetchrow(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref,
                        pp.q50 AS latest_q50
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_key = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at DESC
                ),
                prev AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref,
                        pp.q50 AS prev_q50
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_key = pp.item_ref
                    WHERE i.user_id = $1
                      AND pp.generated_at <= $2
                    ORDER BY pp.item_ref, pp.generated_at DESC
                ),
                combined AS (
                    SELECT
                        l.item_ref,
                        l.latest_q50,
                        COALESCE(p.prev_q50, l.latest_q50) AS prev_q50,
                        ABS(l.latest_q50 - COALESCE(p.prev_q50, l.latest_q50)) AS abs_change
                    FROM latest l
                    LEFT JOIN prev p ON p.item_ref = l.item_ref
                ),
                mover AS (
                    SELECT item_ref, latest_q50, prev_q50
                    FROM combined
                    ORDER BY abs_change DESC
                    LIMIT 1
                )
                SELECT
                    COALESCE(SUM(c.latest_q50), 0)   AS collection_value,
                    COALESCE(SUM(c.prev_q50), 0)     AS yesterday_value,
                    COALESCE(
                        (SELECT COALESCE(i.title, i.canonical_key, i.id::text)
                         FROM mover m JOIN items i ON i.canonical_key = m.item_ref),
                        '--'
                    ) AS biggest_mover_name,
                    COALESCE(
                        (SELECT m.latest_q50 - m.prev_q50 FROM mover m),
                        0
                    ) AS biggest_mover_change
                FROM combined c
                """,
                user_id,
                yesterday,
            )

            collection_value = float(row["collection_value"]) if row else 0.0
            yesterday_value = float(row["yesterday_value"]) if row else 0.0
            today_change = collection_value - yesterday_value
            biggest_name = row["biggest_mover_name"] if row else "--"
            biggest_change = float(row["biggest_mover_change"]) if row else 0.0

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
