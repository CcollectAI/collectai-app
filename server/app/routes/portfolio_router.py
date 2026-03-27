"""
Portfolio router.

Provides portfolio timeseries, overview, and items data.
Queries the DB directly (price_predictions + items tables) with
a fallback to the Signals micro-service proxy when available.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user_id
from app.errors import error_response
from app.config import API_SHARED_SECRET, SIGNALS_BASE_URL
from app.rate_limit import per_user_rate_limit
from app.lib.db_helpers import get_db_pool

router = APIRouter(tags=["Portfolio"])

_logger = logging.getLogger(__name__)

# Per-user: 20 requests per minute for portfolio endpoints
_portfolio_user_limit = per_user_rate_limit(20, scope="portfolio")

# Module-level httpx client — created lazily, closed by lifespan shutdown
_http_client: httpx.AsyncClient | None = None

RANGE_DAYS = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365, "all": 3650}


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def close_http_client() -> None:
    """Close the module-level httpx client. Called during app shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---- Helpers ----

async def _proxy_signals(path: str) -> dict:
    """Proxy a request to the Signals service with error handling."""
    try:
        client = _get_http_client()
        r = await client.get(
            f"{SIGNALS_BASE_URL}{path}",
            headers={"X-API-Key": API_SHARED_SECRET},
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        _logger.error("Upstream %s returned %d", path, e.response.status_code)
        raise error_response(502, "Upstream service error")
    except httpx.RequestError as e:
        _logger.error("Upstream %s request failed: %s", path, e)
        raise error_response(503, "Upstream service unavailable")


# ---- Endpoints ----

@router.get(
    "/portfolio/timeseries",
    dependencies=[Depends(_portfolio_user_limit)],
    summary="Get portfolio value timeseries",
)
async def portfolio_timeseries(
    range: str = Query("30d", pattern="^(1d|7d|30d|90d|1y|all)$"),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Returns daily portfolio value snapshots from price_predictions.

    Aggregates SUM(q50) per day for all user items with predictions.
    Falls back to Signals proxy if DB is unavailable.
    """
    pool = get_db_pool()
    if not pool:
        try:
            return await _proxy_signals(f"/portfolio/timeseries?range={range}")
        except Exception as exc:
            _logger.debug("portfolio fallback failed: %s", exc)
            return {"points": []}

    days = RANGE_DAYS.get(range, 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    DATE(pp.asof) AS day,
                    COALESCE(SUM(pp.q50), 0) AS total_value
                FROM price_predictions pp
                JOIN items i ON i.id = pp.item_id
                WHERE i.user_id = $1
                  AND pp.asof >= $2
                GROUP BY DATE(pp.asof)
                ORDER BY day ASC
                """,
                user_id,
                since,
            )

            points = [
                {"t": row["day"].isoformat(), "v": round(float(row["total_value"]), 2)}
                for row in rows
            ]

            return {"points": points}
    except Exception as e:
        _logger.error("[portfolio/timeseries] DB error: %s", e)
        try:
            return await _proxy_signals(f"/portfolio/timeseries?range={range}")
        except Exception as exc:
            _logger.debug("portfolio fallback failed: %s", exc)
            return {"points": []}


@router.get(
    "/portfolio/overview",
    dependencies=[Depends(_portfolio_user_limit)],
    summary="Get portfolio overview",
)
async def portfolio_overview(user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Returns portfolio overview: total value, item count, top movers.
    Falls back to Signals proxy if DB unavailable.
    """
    pool = get_db_pool()
    if not pool:
        try:
            return await _proxy_signals("/portfolio/overview")
        except Exception as exc:
            _logger.debug("portfolio fallback failed: %s", exc)
            return {"total_value": 0, "item_count": 0, "items": []}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id, pp.q50, pp.asof
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                    ORDER BY pp.item_id, pp.asof DESC
                ),
                prev AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id, pp.q50 AS prev_q50
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                      AND pp.asof < CURRENT_DATE
                    ORDER BY pp.item_id, pp.asof DESC
                )
                SELECT
                    i.id, i.name, i.category,
                    COALESCE(l.q50, 0) AS current_value,
                    COALESCE(p.prev_q50, l.q50, 0) AS prev_value
                FROM items i
                LEFT JOIN latest l ON l.item_id = i.id
                LEFT JOIN prev p ON p.item_id = i.id
                WHERE i.user_id = $1
                ORDER BY COALESCE(l.q50, 0) DESC
                """,
                user_id,
            )

            items = []
            total = 0.0
            for r in rows:
                cv = float(r["current_value"] or 0)
                pv = float(r["prev_value"] or 0)
                change = ((cv - pv) / pv) if pv > 0 else 0.0
                total += cv
                items.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"] or "uncategorized",
                    "current_value": round(cv, 2),
                    "change_1d_pct": round(change, 4),
                })

            return {
                "total_value": round(total, 2),
                "item_count": len(items),
                "items": items,
            }
    except Exception as e:
        _logger.error("[portfolio/overview] DB error: %s", e)
        try:
            return await _proxy_signals("/portfolio/overview")
        except Exception as exc:
            _logger.debug("portfolio fallback failed: %s", exc)
            return {"total_value": 0, "item_count": 0, "items": []}


@router.get(
    "/portfolio/items",
    dependencies=[Depends(_portfolio_user_limit)],
    summary="Get portfolio items with valuations",
)
async def portfolio_items(user_id: str = Depends(get_current_user_id)) -> dict:
    """Portfolio items with latest + earliest predictions for P/L calc."""
    pool = get_db_pool()
    if not pool:
        try:
            return await _proxy_signals("/portfolio/items")
        except Exception as exc:
            _logger.debug("portfolio fallback failed: %s", exc)
            return {"items": []}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id, pp.q50, pp.q10, pp.q90
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                    ORDER BY pp.item_id, pp.asof DESC
                ),
                earliest AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id, pp.q50 AS first_q50
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                    ORDER BY pp.item_id, pp.asof ASC
                )
                SELECT
                    i.id, i.name, i.category,
                    COALESCE(l.q50, 0) AS current_value,
                    COALESCE(l.q10, 0) AS q10,
                    COALESCE(l.q90, 0) AS q90,
                    COALESCE(e.first_q50, 0) AS cost_basis
                FROM items i
                LEFT JOIN latest l ON l.item_id = i.id
                LEFT JOIN earliest e ON e.item_id = i.id
                WHERE i.user_id = $1
                ORDER BY COALESCE(l.q50, 0) DESC
                """,
                user_id,
            )

            items = []
            for r in rows:
                cv = float(r["current_value"] or 0)
                cb = float(r["cost_basis"] or 0)
                items.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"] or "uncategorized",
                    "current_value": round(cv, 2),
                    "cost_basis": round(cb, 2),
                    "unrealized_pl": round(cv - cb, 2),
                    "q10": round(float(r["q10"] or 0), 2),
                    "q90": round(float(r["q90"] or 0), 2),
                })

            return {"items": items}
    except Exception as e:
        _logger.error("[portfolio/items] DB error: %s", e)
        try:
            return await _proxy_signals("/portfolio/items")
        except Exception as exc:
            _logger.debug("portfolio fallback failed: %s", exc)
            return {"items": []}


@router.get("/portfolio/summary", summary="Get portfolio summary")
async def portfolio_summary(user_id: str = Depends(get_current_user_id)) -> dict:
    """Lightweight portfolio summary. Uses DB when available, else demo items."""
    pool = get_db_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) AS item_count,
                        COALESCE(SUM(lp.q50), 0) AS total_value
                    FROM items i
                    LEFT JOIN LATERAL (
                        SELECT q50 FROM price_predictions pp
                        WHERE pp.item_id = i.id
                        ORDER BY pp.asof DESC LIMIT 1
                    ) lp ON TRUE
                    WHERE i.user_id = $1
                    """,
                    user_id,
                )
                return {
                    "total_value": round(float(row["total_value"] or 0), 2),
                    "avg_change_pct": 0.0,
                    "items": [],
                    "watchlist": [],
                }
        except Exception as e:
            _logger.warning("[portfolio/summary] DB error, falling back: %s", e)

    # Fallback to demo items
    from app.routes.items_router import get_demo_items

    items_payload = []
    try:
        for it in get_demo_items():
            try:
                value = float(it.estimated_value or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            items_payload.append({
                "id": it.id,
                "name": it.name,
                "category": it.category or "Uncategorized",
                "value": value,
                "change_pct": 0.0,
            })
    except Exception as e:
        _logger.warning("[portfolio_summary] demo items unavailable: %s", e)

    total_value = sum(i["value"] for i in items_payload) if items_payload else 0.0

    return {
        "total_value": total_value,
        "avg_change_pct": 0.0,
        "items": items_payload,
        "watchlist": [],
    }


# ── H1: Category Statistics ─────────────────────────────────────────────


@router.get(
    "/portfolio/category-stats",
    dependencies=[Depends(_portfolio_user_limit)],
    summary="Per-category portfolio statistics",
)
async def portfolio_category_stats(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Returns per-category stats: item count, total value, avg value,
    top mover (biggest 1d change), and 7d price trend direction.
    """
    pool = get_db_pool()
    if not pool:
        return {"categories": []}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id, pp.q50, pp.asof
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                    ORDER BY pp.item_id, pp.asof DESC
                ),
                prev_7d AS (
                    SELECT DISTINCT ON (pp.item_id)
                        pp.item_id, pp.q50 AS q50_7d
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                      AND pp.asof <= NOW() - INTERVAL '7 days'
                    ORDER BY pp.item_id, pp.asof DESC
                )
                SELECT
                    i.category,
                    COUNT(*) AS item_count,
                    COALESCE(SUM(l.q50), 0) AS total_value,
                    COALESCE(AVG(l.q50), 0) AS avg_value,
                    COALESCE(SUM(l.q50), 0) - COALESCE(SUM(p.q50_7d), 0) AS change_7d,
                    MAX(l.q50) AS max_item_value
                FROM items i
                LEFT JOIN latest l ON l.item_id = i.id
                LEFT JOIN prev_7d p ON p.item_id = i.id
                WHERE i.user_id = $1
                  AND i.category IS NOT NULL
                GROUP BY i.category
                ORDER BY COALESCE(SUM(l.q50), 0) DESC
                """,
                user_id,
            )

            categories = []
            for r in rows:
                tv = float(r["total_value"] or 0)
                c7 = float(r["change_7d"] or 0)
                trend = "up" if c7 > 0 else ("down" if c7 < 0 else "flat")
                categories.append({
                    "category": r["category"],
                    "item_count": int(r["item_count"]),
                    "total_value": round(tv, 2),
                    "avg_value": round(float(r["avg_value"] or 0), 2),
                    "change_7d": round(c7, 2),
                    "change_7d_pct": round(c7 / tv * 100, 2) if tv > 0 else 0.0,
                    "trend": trend,
                    "max_item_value": round(float(r["max_item_value"] or 0), 2),
                })

            return {"categories": categories}
    except Exception as e:
        _logger.error("[portfolio/category-stats] DB error: %s", e)
        return {"categories": []}


# ── M4: Category Health Indicators ──────────────────────────────────────


@router.get(
    "/portfolio/category-health",
    dependencies=[Depends(_portfolio_user_limit)],
    summary="Category health indicators (liquidity, volatility)",
)
async def category_health(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Returns health indicators per category the user holds:
    - volatility: stddev of daily value changes over 30d
    - liquidity_score: number of market_hits in last 7d (proxy)
    - trend_strength: ratio of current vs 30d-ago value
    """
    pool = get_db_pool()
    if not pool:
        return {"health": []}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH user_cats AS (
                    SELECT DISTINCT category
                    FROM items
                    WHERE user_id = $1 AND category IS NOT NULL
                ),
                daily_vals AS (
                    SELECT
                        i.category,
                        DATE(pp.asof) AS day,
                        SUM(pp.q50) AS day_val
                    FROM price_predictions pp
                    JOIN items i ON i.id = pp.item_id
                    WHERE i.user_id = $1
                      AND pp.asof >= NOW() - INTERVAL '30 days'
                    GROUP BY i.category, DATE(pp.asof)
                ),
                stats AS (
                    SELECT
                        category,
                        STDDEV(day_val) AS volatility,
                        FIRST_VALUE(day_val) OVER (
                            PARTITION BY category ORDER BY day ASC
                        ) AS val_30d_ago,
                        LAST_VALUE(day_val) OVER (
                            PARTITION BY category
                            ORDER BY day ASC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                        ) AS val_now
                    FROM daily_vals
                )
                SELECT DISTINCT
                    s.category,
                    COALESCE(s.volatility, 0) AS volatility,
                    COALESCE(s.val_now, 0) AS val_now,
                    COALESCE(s.val_30d_ago, 0) AS val_30d_ago
                FROM stats s
                JOIN user_cats uc ON uc.category = s.category
                """,
                user_id,
            )

            health = []
            for r in rows:
                vn = float(r["val_now"] or 0)
                v30 = float(r["val_30d_ago"] or 0)
                vol = float(r["volatility"] or 0)
                trend_str = round(vn / v30, 2) if v30 > 0 else 1.0
                # Health: green if low vol + uptrend, yellow if moderate, red if high vol or downtrend
                score = "green"
                if vol > vn * 0.1 or trend_str < 0.95:
                    score = "yellow"
                if vol > vn * 0.2 or trend_str < 0.85:
                    score = "red"

                health.append({
                    "category": r["category"],
                    "volatility": round(vol, 2),
                    "trend_strength": trend_str,
                    "health": score,
                })

            return {"health": health}
    except Exception as e:
        _logger.error("[portfolio/category-health] DB error: %s", e)
        return {"health": []}


# ── L2: Cross-Category Correlation ──────────────────────────────────────


@router.get(
    "/portfolio/category-correlation",
    dependencies=[Depends(_portfolio_user_limit)],
    summary="Cross-category collector overlap",
)
async def category_correlation(
    category: str = Query(..., min_length=1, max_length=80),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    For a given category, find other categories that the same collectors
    tend to own. Returns overlap percentages.
    """
    pool = get_db_pool()
    if not pool:
        return {"correlations": []}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH cat_users AS (
                    SELECT DISTINCT user_id
                    FROM items
                    WHERE category = $1
                ),
                cat_user_count AS (
                    SELECT COUNT(*) AS cnt FROM cat_users
                ),
                other_cats AS (
                    SELECT
                        i.category,
                        COUNT(DISTINCT i.user_id) AS overlap_count
                    FROM items i
                    JOIN cat_users cu ON cu.user_id = i.user_id
                    WHERE i.category IS NOT NULL
                      AND i.category != $1
                    GROUP BY i.category
                )
                SELECT
                    oc.category,
                    oc.overlap_count AS collector_count,
                    ROUND(oc.overlap_count::numeric / GREATEST(cuc.cnt, 1) * 100, 1) AS overlap_pct
                FROM other_cats oc, cat_user_count cuc
                ORDER BY oc.overlap_count DESC
                LIMIT 10
                """,
                category,
            )

            correlations = [
                {
                    "category": r["category"],
                    "collector_count": int(r["collector_count"]),
                    "overlap_pct": float(r["overlap_pct"]),
                }
                for r in rows
            ]

            return {"correlations": correlations}
    except Exception as e:
        _logger.error("[portfolio/category-correlation] DB error: %s", e)
        return {"correlations": []}
