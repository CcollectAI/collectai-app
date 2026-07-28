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
                    DATE(pp.generated_at) AS day,
                    COALESCE(SUM(pp.q50), 0) AS total_value
                FROM price_predictions pp
                JOIN items i ON i.canonical_ref = pp.item_ref
                WHERE i.user_id = $1
                  AND pp.generated_at >= $2
                GROUP BY DATE(pp.generated_at)
                ORDER BY day ASC
                """,
                user_id,
                since,
            )

            points = [
                {"t": row["day"].isoformat(), "v": round(float(row["total_value"]), 2)}
                for row in rows
            ]

            # Flat-baseline fallback. Portfolios whose items have no dated
            # price_predictions (e.g. hand-added items carrying only a stored
            # value) produce zero prediction rows → an empty curve → the FE shows
            # "No history yet". Instead draw a flat line at the CURRENT stored
            # portfolio value across the range so the graph always reflects the
            # collection's worth. Same value source as /portfolio/overview
            # (COALESCE q50 → predicted_price_eur → estimated_value). This is a
            # synthetic baseline until real history (predictions or a daily
            # snapshot worker) accrues; a genuinely empty portfolio (value 0)
            # still yields no points so the honest empty state remains.
            if len(points) < 2:
                cur = await conn.fetchval(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (pp.item_ref) pp.item_ref, pp.q50
                        FROM price_predictions pp
                        JOIN items i ON i.canonical_ref = pp.item_ref
                        WHERE i.user_id = $1
                        ORDER BY pp.item_ref, pp.generated_at DESC
                    )
                    SELECT COALESCE(SUM(
                        COALESCE(l.q50, i.predicted_price_eur, i.estimated_value, 0)
                    ), 0)
                    FROM items i
                    LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                    WHERE i.user_id = $1
                    """,
                    user_id,
                )
                cur_v = round(float(cur or 0), 2)
                if cur_v > 0:
                    today = datetime.now(timezone.utc)
                    points = [
                        {"t": since.date().isoformat(), "v": cur_v},
                        {"t": today.date().isoformat(), "v": cur_v},
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
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50, pp.generated_at
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at DESC
                ),
                prev AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50 AS prev_q50
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                      AND pp.generated_at < CURRENT_DATE
                    ORDER BY pp.item_ref, pp.generated_at DESC
                )
                SELECT
                    i.id, i.name, i.category,
                    -- Match the category-breakdown / Items-tab value source: a
                    -- model prediction if one exists, else the item's own stored
                    -- value (predicted_price_eur / estimated_value). Without this
                    -- fallback, hand-added items with no price_predictions row
                    -- valued at 0 here while the Items tab showed their stored
                    -- price — Home's "COLLECTION VALUE" read €0 vs €55 elsewhere.
                    COALESCE(l.q50, i.predicted_price_eur, i.estimated_value, 0) AS current_value,
                    COALESCE(p.prev_q50, l.q50, i.predicted_price_eur, i.estimated_value, 0) AS prev_value
                FROM items i
                LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                LEFT JOIN prev p ON p.item_ref = i.canonical_ref
                WHERE i.user_id = $1
                ORDER BY COALESCE(l.q50, i.predicted_price_eur, i.estimated_value, 0) DESC
                """,
                user_id,
            )

            items = []
            total = 0.0
            total_prev = 0.0
            for r in rows:
                cv = float(r["current_value"] or 0)
                pv = float(r["prev_value"] or 0)
                change = ((cv - pv) / pv) if pv > 0 else 0.0
                total += cv
                # Fall back to cv so an item with no prior valuation contributes
                # 0% rather than a phantom +100% to the portfolio-level change.
                total_prev += pv if pv > 0 else cv
                items.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"] or "uncategorized",
                    "current_value": round(cv, 2),
                    "change_1d_pct": round(change, 4),
                })

            # Portfolio-level change. Added 2026-07-24: the FE's
            # getPortfolioSummary derived this from `portfolio_values`, a table
            # with no writer anywhere (0 rows), so Home's insights card showed
            # +0.00% / EUR 0 change no matter what the collection did. Serving
            # it here reuses the same COALESCE valuation the totals use.
            total_change = ((total - total_prev) / total_prev) if total_prev > 0 else 0.0

            return {
                "total_value": round(total, 2),
                "total_prev_value": round(total_prev, 2),
                "change_1d_pct": round(total_change, 4),
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
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50, pp.q10, pp.q90
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at DESC
                ),
                earliest AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50 AS first_q50
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at ASC
                )
                SELECT
                    i.id, i.name, i.category,
                    COALESCE(l.q50, 0) AS current_value,
                    COALESCE(l.q10, 0) AS q10,
                    COALESCE(l.q90, 0) AS q90,
                    -- What the user actually PAID, falling back to the earliest
                    -- prediction only when there is no purchase price on file.
                    -- This was `COALESCE(e.first_q50, 0)` alone, which made
                    -- unrealized_pl = current_value - first_predicted_value:
                    -- model drift, not profit. Someone who paid EUR 50 for an
                    -- item now worth EUR 200 saw ~0 P/L whenever the model had
                    -- been stable. Unfixable until 2026-07-28, because
                    -- purchase_price_eur was non-null on 0 of 5 priced rows;
                    -- see the paired-columns note in docs/ARCHITECTURE.md.
                    -- The EUR half is the right one: current_value is q50,
                    -- which is EUR, so summing raw purchase_price here would
                    -- mix currencies on the same axis.
                    COALESCE(i.purchase_price_eur, e.first_q50, 0) AS cost_basis
                FROM items i
                LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                LEFT JOIN earliest e ON e.item_ref = i.canonical_ref
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
                        WHERE pp.item_ref = i.canonical_ref
                        ORDER BY pp.generated_at DESC LIMIT 1
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
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50, pp.generated_at
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                    ORDER BY pp.item_ref, pp.generated_at DESC
                ),
                prev_7d AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50 AS q50_7d
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                      AND pp.generated_at <= NOW() - INTERVAL '7 days'
                    ORDER BY pp.item_ref, pp.generated_at DESC
                )
                SELECT
                    i.category,
                    COUNT(*) AS item_count,
                    COALESCE(SUM(l.q50), 0) AS total_value,
                    COALESCE(AVG(l.q50), 0) AS avg_value,
                    COALESCE(SUM(l.q50), 0) - COALESCE(SUM(p.q50_7d), 0) AS change_7d,
                    MAX(l.q50) AS max_item_value
                FROM items i
                LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                LEFT JOIN prev_7d p ON p.item_ref = i.canonical_ref
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
                        DATE(pp.generated_at) AS day,
                        SUM(pp.q50) AS day_val
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                      AND pp.generated_at >= NOW() - INTERVAL '30 days'
                    GROUP BY i.category, DATE(pp.generated_at)
                ),
                -- Volatility (an aggregate) and the first/last values (window
                -- functions) MUST be computed in separate CTEs. Selecting
                -- STDDEV(day_val) alongside a bare `category` and two OVER()
                -- expressions with no GROUP BY is invalid SQL, and Postgres
                -- rejected it every single call:
                --   column "daily_vals.category" must appear in the GROUP BY
                --   clause or be used in an aggregate function
                -- The except below logs it, but still returns {"health": []}
                -- with HTTP 200 — so from the client's side the endpoint looked
                -- healthy and merely empty, and the Category Health card never
                -- rendered for anyone. Fixed 2026-07-25; it was showing up
                -- 13x/day in the Supabase Postgres logs.
                vol AS (
                    SELECT category, STDDEV(day_val) AS volatility
                    FROM daily_vals
                    GROUP BY category
                ),
                edges AS (
                    SELECT DISTINCT ON (category)
                        category,
                        FIRST_VALUE(day_val) OVER w AS val_30d_ago,
                        LAST_VALUE(day_val)  OVER w AS val_now
                    FROM daily_vals
                    WINDOW w AS (
                        PARTITION BY category
                        ORDER BY day ASC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                    )
                )
                SELECT
                    v.category,
                    COALESCE(v.volatility, 0) AS volatility,
                    COALESCE(e.val_now, 0) AS val_now,
                    COALESCE(e.val_30d_ago, 0) AS val_30d_ago
                FROM vol v
                JOIN edges e ON e.category = v.category
                JOIN user_cats uc ON uc.category = v.category
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
