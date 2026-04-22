"""
Data moat helpers — supply tracking + demand signal recording.

These functions are called from various routers to build proprietary data
that strengthens model accuracy over time.

Supply snapshots:  Record listing counts per item/category after each crawl.
Demand signals:    Record user intent signals (searches, mandates, views).

REST endpoints (mounted via router):
- GET /data-moat/supply-trends?category=...&item_key=...
- GET /data-moat/demand-heat?category=...
- GET /data-moat/health
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.lib.validators import is_valid_category
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-moat", tags=["Data Moat"])

_data_moat_limit = per_user_rate_limit(30, window_seconds=60, scope="data_moat")


def _to_uuid_or_none(s: str | None) -> UUID | None:
    """Convert string to UUID, returning None if invalid."""
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, AttributeError):
        return None


async def get_user_geo(user_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Look up user's region and country from user_settings (best-effort).

    Returns (region, country_code) or (None, None) if unavailable.
    """
    if not user_id:
        return None, None
    pool = get_db_pool()
    if pool is None:
        return None, None
    try:
        uid = _to_uuid_or_none(user_id)
        if uid is None:
            return None, None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT region FROM user_settings WHERE user_id = $1",
                uid,
            )
            if row and row["region"]:
                # Map region name to code for country_code field
                _REGION_TO_CODE = {
                    "americas": "US", "europe": "EU", "asia": "JP",
                    "oceania": "AU", "other": None,
                }
                return row["region"], _REGION_TO_CODE.get(row["region"])
    except Exception as e:
        logger.debug("[data_moat] get_user_geo lookup failed: %s", e)
    return None, None


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
    pool = get_db_pool()
    if pool is None:
        return False

    try:
        async with pool.acquire() as conn:
            # Dedup: skip insert if a snapshot already exists for the same
            # category/item_key/source within the current hour.
            await conn.execute(
                """
                INSERT INTO public.supply_snapshots
                    (category, item_key, source, listing_count,
                     avg_price_eur, min_price_eur, max_price_eur, metadata)
                SELECT $1, $2, $3, $4, $5, $6, $7, $8::jsonb
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.supply_snapshots
                    WHERE category = $1
                      AND item_key = $2
                      AND source = $3
                      AND snapshot_at >= date_trunc('hour', now())
                )
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
    region: Optional[str] = None,
    country_code: Optional[str] = None,
) -> bool:
    """
    Record a demand signal from a user action.

    Signal types:
    - mandate_created:   User created a purchase mandate for an item
    - search_query:      User searched for items/categories
    - item_viewed:       User viewed item detail / dossier / price evidence
    - price_alert_set:   User set a price alert
    - watchlist_add:     User added item to watchlist
    - item_scanned:      User scanned/photographed item via intake
    - item_added:        User added item to their collection
    - catalog_browsed:   User browsed category catalog
    - category_viewed:   User opened category deep-dive analytics
    - collection_viewed: User viewed a specific collection/set

    Called from routers across the entire user journey.

    Optional geo fields (region, country_code) enable geographic demand
    segmentation when available.

    Returns True if recorded, False on failure.
    """
    pool = get_db_pool()
    if pool is None:
        return False

    valid_types = {
        "mandate_created", "search_query", "item_viewed",
        "price_alert_set", "watchlist_add",
        "item_scanned", "item_added", "catalog_browsed",
        "category_viewed", "collection_viewed",
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
                    (signal_type, category, item_key, query_text, user_id,
                     region, country_code)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                signal_type,
                category,
                item_key,
                query_text,
                uid,
                region,
                country_code,
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
    pool = get_db_pool()
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
    pool = get_db_pool()
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


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/supply-trends")
async def supply_trends_endpoint(
    category: str = Query(..., min_length=1, max_length=64),
    item_key: str = Query(..., min_length=1, max_length=255),
    days: int = Query(30, ge=1, le=365),
    _user: str = Depends(get_current_user_id),
    _rl: None = Depends(_data_moat_limit),
):
    """Supply trend for an item over the last N days."""
    # R48.5 — accept custom categories (no validation gate). Demand/supply
    # signals should accumulate for ANY category including user-created ones.
    # This powers the flywheel: popular custom categories surface in the admin
    # demand dashboard and become candidates for official support.
    data = await get_supply_trend(category, item_key, days)
    return {"category": category, "item_key": item_key, "days": days, "trends": data}


@router.get("/demand-heat")
async def demand_heat_endpoint(
    category: Optional[str] = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=100),
    _user: str = Depends(get_current_user_id),
    _rl: None = Depends(_data_moat_limit),
):
    """Top trending items by demand signal volume."""
    # R48.5 — same as above, accept any category
    data = await get_demand_heat(category, limit)
    return {"category": category, "limit": limit, "items": data}


@router.get("/health")
async def data_moat_health(
    _user: str = Depends(get_current_user_id),
):
    """Data moat system health: signal counts, last timestamps, view freshness."""
    pool = get_db_pool()
    if pool is None:
        # 503 surfaces the failure to callers/monitors; previously returned
        # HTTP 200 with ok:False which every caller treats as a success.
        raise HTTPException(status_code=503, detail="no_db_pool")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    (SELECT max(snapshot_at) FROM supply_snapshots) AS last_supply,
                    (SELECT count(*) FROM supply_snapshots) AS supply_count,
                    (SELECT max(created_at) FROM demand_signals) AS last_demand,
                    (SELECT count(*) FROM demand_signals) AS demand_count
                """
            )

            # Signal counts per category (top 10)
            cat_rows = await conn.fetch(
                """
                SELECT category, count(*) AS cnt
                FROM demand_signals
                WHERE created_at > now() - interval '7 days'
                GROUP BY category
                ORDER BY cnt DESC
                LIMIT 10
                """
            )

            # Check view freshness by querying the views
            supply_view_count = 0
            demand_view_count = 0
            try:
                sv = await conn.fetchval("SELECT count(*) FROM mv_supply_trend")
                supply_view_count = sv or 0
            except Exception as e:
                logger.debug("[data_moat] mv_supply_trend count failed: %s", e)
            try:
                dv = await conn.fetchval("SELECT count(*) FROM mv_demand_heat")
                demand_view_count = dv or 0
            except Exception as e:
                logger.debug("[data_moat] mv_demand_heat count failed: %s", e)

            return {
                "ok": True,
                "last_supply_snapshot": row["last_supply"].isoformat() if row["last_supply"] else None,
                "supply_snapshot_count": row["supply_count"],
                "last_demand_signal": row["last_demand"].isoformat() if row["last_demand"] else None,
                "demand_signal_count": row["demand_count"],
                "signals_per_category_7d": {
                    r["category"]: r["cnt"] for r in cat_rows
                },
                "mv_supply_trend_rows": supply_view_count,
                "mv_demand_heat_rows": demand_view_count,
            }
    except Exception as e:
        logger.error("[data_moat/health] DB error: %s", e)
        raise HTTPException(status_code=500, detail=f"db_error: {e}")


# ---------------------------------------------------------------------------
# Feature 2: Price Accuracy Feedback Loop
# ---------------------------------------------------------------------------

async def record_price_ground_truth(
    item_id: str,
    actual_price: float,
    currency: str = "EUR",
    source: str = "deal_desk",
) -> bool:
    """
    Record an actual transaction price as ground truth.

    Called when a Deal Desk offer completes. Compares against the most recent
    price_prediction for the item to compute prediction error, which feeds
    back into model calibration.

    Returns True if recorded, False on failure.
    """
    pool = get_db_pool()
    if pool is None:
        return False

    try:
        async with pool.acquire() as conn:
            # Fetch latest prediction for this item
            pred = await conn.fetchrow(
                """
                SELECT q50, q10, q90, conf_score, asof
                FROM price_predictions
                WHERE item_id = $1::uuid
                ORDER BY asof DESC
                LIMIT 1
                """,
                item_id,
            )

            prediction_q50 = float(pred["q50"]) if pred and pred["q50"] else None
            error_pct = None
            if prediction_q50 and prediction_q50 > 0:
                error_pct = round((actual_price - prediction_q50) / prediction_q50, 4)

            await conn.execute(
                """
                INSERT INTO public.price_ground_truths
                    (item_id, actual_price, currency, source,
                     prediction_q50, error_pct)
                VALUES ($1::uuid, $2, $3, $4, $5, $6)
                """,
                item_id,
                actual_price,
                currency,
                source,
                prediction_q50,
                error_pct,
            )
        logger.info(
            "[data_moat] Ground truth recorded: item=%s price=%.2f error=%.1f%%",
            item_id, actual_price, (error_pct or 0) * 100,
        )
        return True
    except Exception as e:
        logger.warning("[data_moat] Failed to record ground truth: %s", e)
        return False


@router.get("/prediction-accuracy")
async def prediction_accuracy(
    category: Optional[str] = Query(None, max_length=64),
    days: int = Query(30, ge=1, le=365),
    _user: str = Depends(get_current_user_id),
    _rl: None = Depends(_data_moat_limit),
):
    """
    Prediction accuracy metrics from ground truth data.

    Returns MAE, median error, hit rate (actual within q10-q90 band).
    """
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")

    try:
        async with pool.acquire() as conn:
            cat_filter = ""
            params: list = [days]
            if category:
                cat_filter = "AND i.category = $2"
                params.append(category)

            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS total,
                    AVG(ABS(gt.error_pct)) AS mae,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gt.error_pct) AS median_error,
                    COUNT(*) FILTER (
                        WHERE gt.actual_price BETWEEN
                            COALESCE(pp.q10, gt.prediction_q50 * 0.8)
                            AND COALESCE(pp.q90, gt.prediction_q50 * 1.2)
                    ) AS in_band
                FROM price_ground_truths gt
                JOIN items i ON i.id = gt.item_id
                LEFT JOIN LATERAL (
                    SELECT q10, q90 FROM price_predictions pp2
                    WHERE pp2.item_ref = i.canonical_key
                    ORDER BY pp2.generated_at DESC LIMIT 1
                ) pp ON true
                WHERE gt.recorded_at >= now() - make_interval(days => $1)
                  {cat_filter}
                """,
                *params,
            )

            total = int(row["total"] or 0)
            return {
                "category": category,
                "days": days,
                "total_ground_truths": total,
                "mae_pct": round(float(row["mae"] or 0), 4),
                "median_error_pct": round(float(row["median_error"] or 0), 4),
                "band_hit_rate": round(int(row["in_band"] or 0) / total, 4) if total > 0 else None,
            }
    except Exception as e:
        logger.error("[data_moat/prediction-accuracy] DB error: %s", e)
        raise HTTPException(status_code=500, detail=f"db_error: {e}")


# ---------------------------------------------------------------------------
# Feature 3: Scarcity Detection
# ---------------------------------------------------------------------------

async def detect_scarcity(
    min_demand_signals: int = 5,
    min_supply_decline_pct: float = 0.20,
    days: int = 14,
) -> list[dict]:
    """
    Detect items where supply is dropping while demand is rising.

    Scarcity score = demand_growth × supply_decline (both normalized 0-1).
    Higher score = stronger scarcity signal.
    """
    pool = get_db_pool()
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH demand AS (
                    SELECT
                        category,
                        item_key,
                        COUNT(*) FILTER (WHERE created_at >= now() - ($1 || ' days')::interval) AS recent_signals,
                        COUNT(*) FILTER (WHERE created_at < now() - ($1 || ' days')::interval
                                           AND created_at >= now() - ($1 * 2 || ' days')::interval) AS prev_signals
                    FROM demand_signals
                    WHERE item_key IS NOT NULL
                      AND created_at >= now() - ($1 * 2 || ' days')::interval
                    GROUP BY category, item_key
                    HAVING COUNT(*) FILTER (WHERE created_at >= now() - ($1 || ' days')::interval) >= $2
                ),
                supply AS (
                    SELECT
                        category,
                        item_key,
                        AVG(listing_count) FILTER (WHERE snapshot_at >= now() - ($1 || ' days')::interval) AS recent_supply,
                        AVG(listing_count) FILTER (WHERE snapshot_at < now() - ($1 || ' days')::interval
                                                     AND snapshot_at >= now() - ($1 * 2 || ' days')::interval) AS prev_supply
                    FROM supply_snapshots
                    WHERE snapshot_at >= now() - ($1 * 2 || ' days')::interval
                    GROUP BY category, item_key
                )
                SELECT
                    d.category,
                    d.item_key,
                    d.recent_signals,
                    d.prev_signals,
                    s.recent_supply,
                    s.prev_supply,
                    CASE WHEN d.prev_signals > 0
                         THEN (d.recent_signals - d.prev_signals)::float / d.prev_signals
                         ELSE 1.0
                    END AS demand_growth,
                    CASE WHEN s.prev_supply > 0
                         THEN (s.prev_supply - s.recent_supply)::float / s.prev_supply
                         ELSE 0.0
                    END AS supply_decline
                FROM demand d
                LEFT JOIN supply s ON s.category = d.category AND s.item_key = d.item_key
                WHERE s.prev_supply IS NULL
                   OR (s.prev_supply > 0
                       AND (s.prev_supply - COALESCE(s.recent_supply, 0)) / s.prev_supply >= $3)
                ORDER BY d.recent_signals DESC
                LIMIT 20
                """,
                days,
                min_demand_signals,
                min_supply_decline_pct,
            )

        return [
            {
                "category": r["category"],
                "item_key": r["item_key"],
                "recent_demand": r["recent_signals"],
                "prev_demand": r["prev_signals"],
                "demand_growth_pct": round(float(r["demand_growth"] or 0), 3),
                "recent_supply": float(r["recent_supply"]) if r["recent_supply"] else None,
                "prev_supply": float(r["prev_supply"]) if r["prev_supply"] else None,
                "supply_decline_pct": round(float(r["supply_decline"] or 0), 3),
                "scarcity_score": round(
                    max(0, float(r["demand_growth"] or 0))
                    * max(0, float(r["supply_decline"] or 0)),
                    3,
                ),
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("[data_moat] Scarcity detection failed: %s", e)
        return []


@router.get("/scarcity")
async def scarcity_endpoint(
    days: int = Query(14, ge=7, le=90),
    _user: str = Depends(get_current_user_id),
    _rl: None = Depends(_data_moat_limit),
):
    """Items becoming scarce: supply dropping + demand rising."""
    data = await detect_scarcity(days=days)
    return {"days": days, "items": data}


# ---------------------------------------------------------------------------
# Feature 4: Geographic Demand Segmentation
# ---------------------------------------------------------------------------

@router.get("/demand-heat/by-region")
async def demand_heat_by_region(
    category: Optional[str] = Query(None, max_length=64),
    days: int = Query(7, ge=1, le=90),
    _user: str = Depends(get_current_user_id),
    _rl: None = Depends(_data_moat_limit),
):
    """Demand heat broken down by geographic region."""
    pool = get_db_pool()
    if pool is None:
        return {"regions": []}

    try:
        async with pool.acquire() as conn:
            cat_filter = ""
            params: list = [days]
            if category:
                cat_filter = "AND category = $2"
                params.append(category)

            rows = await conn.fetch(
                f"""
                SELECT
                    COALESCE(region, 'unknown') AS region,
                    COALESCE(country_code, 'XX') AS country_code,
                    COUNT(*) AS signal_count,
                    COUNT(DISTINCT user_id) AS unique_users,
                    COUNT(DISTINCT item_key) AS unique_items
                FROM demand_signals
                WHERE created_at >= now() - ($1 || ' days')::interval
                  AND region IS NOT NULL
                  {cat_filter}
                GROUP BY region, country_code
                ORDER BY signal_count DESC
                LIMIT 50
                """,
                *params,
            )

            return {
                "category": category,
                "days": days,
                "regions": [
                    {
                        "region": r["region"],
                        "country_code": r["country_code"],
                        "signal_count": r["signal_count"],
                        "unique_users": r["unique_users"],
                        "unique_items": r["unique_items"],
                    }
                    for r in rows
                ],
            }
    except Exception as e:
        logger.error("[data_moat/demand-heat/by-region] DB error: %s", e)
        return {"regions": [], "error": str(e)}
