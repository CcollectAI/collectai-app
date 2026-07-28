from __future__ import annotations

import asyncio
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
from app.lib.bg_tasks import spawn_bg
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
                JOIN items i ON i.canonical_ref = pp.item_ref
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
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1 AND pp.generated_at >= $2
                    ORDER BY i.id, pp.generated_at ASC
                ),
                latest AS (
                    SELECT DISTINCT ON (i.id)
                        i.id AS item_id,
                        i.category,
                        pp.q50 AS last_value
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
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
                            -- EUR half, not the raw one: total_history above
                            -- sums pp.q50 (EUR), so summing raw purchase_price
                            -- here put two different units on one chart -- a
                            -- USD 100 and a EUR 100 each contributed 100.
                            SUM(i.purchase_price_eur) AS day_cost
                        FROM items i
                        WHERE i.user_id = $1
                          AND i.purchase_price_eur IS NOT NULL
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
            # price_predictions has no `asof` or `item_id` — use
            # generated_at + item_ref (= items.canonical_key).
            rows = await conn.fetch(
                """
                SELECT generated_at AS asof, q50, conf_score
                FROM price_predictions
                WHERE item_ref = (SELECT canonical_ref FROM items WHERE id = $1::uuid)
                  AND generated_at >= $2
                ORDER BY generated_at
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
                -- Per-item value MUST match what the Items list card shows,
                -- or the category cards + home "Portfolio" stat disagree with
                -- the item rows / "Collection total" (flagged 2026-07-22:
                -- item = €55 but card/portfolio = €0). The FE reads
                -- COALESCE(latest quick_predictions.q50_eur,
                --          items.predicted_price_eur, items.estimated_value, 0)
                -- (see src/data/providers/itemsProvider.ts mapItemRow) — NOT
                -- price_predictions.q50. Manual / QuickScan items have no
                -- price_predictions row (that table is catalog-model output,
                -- joined by canonical_key), so the old SUM(pp.q50) returned 0
                -- for every hand-added item. Sum the SAME source here.
                -- quick_predictions is a plain (non-partitioned) table keyed
                -- by item_id, so there is no partition-planning cost.
                WITH latest_qp AS (
                    SELECT DISTINCT ON (qp.item_id)
                        qp.item_id,
                        qp.q50_eur,
                        qp.created_at
                    FROM quick_predictions qp
                    JOIN items i2 ON i2.id = qp.item_id
                    WHERE i2.user_id = $1
                    ORDER BY qp.item_id, qp.created_at DESC
                ),
                earliest_qp AS (
                    SELECT DISTINCT ON (qp.item_id)
                        qp.item_id,
                        qp.q50_eur AS first_q50
                    FROM quick_predictions qp
                    JOIN items i2 ON i2.id = qp.item_id
                    WHERE i2.user_id = $1
                    ORDER BY qp.item_id, qp.created_at ASC
                )
                SELECT
                    COALESCE(NULLIF(i.category, ''), 'uncategorized') AS category,
                    COUNT(*) AS item_count,
                    COALESCE(SUM(
                        COALESCE(lq.q50_eur, i.predicted_price_eur, i.estimated_value, 0)
                    ), 0) AS total_value,
                    COALESCE(SUM(
                        COALESCE(eq.first_q50, i.predicted_price_eur, i.estimated_value, 0)
                    ), 0) AS first_total
                FROM items i
                LEFT JOIN latest_qp lq ON lq.item_id = i.id
                LEFT JOIN earliest_qp eq ON eq.item_id = i.id
                WHERE i.user_id = $1
                  -- `AND i.category IS NOT NULL` USED TO BE HERE. It silently
                  -- dropped every item saved without a category — and Category
                  -- is OPTIONAL on the Add-Manually form, so this is a normal
                  -- thing for a user to do.
                  --
                  -- The effect was a headline number that disagreed with
                  -- itself: Home showed "1 Categories / 1 Total Items / €0"
                  -- (globalStatsTotalItems sums this breakdown) while the
                  -- Items tab showed "2 items" with an "Uncategorized" group.
                  -- Reproduced 2026-07-27 by saving an item with no category.
                  --
                  -- That is the exact goal the comment above states — parity
                  -- with the Items list — so bucketing under 'uncategorized'
                  -- restores it rather than widening scope. itemsProvider.ts
                  -- already maps a null category to 'Uncategorized' for
                  -- display, so the FE needs no change.
                  --
                  -- NOTE: intentionally NOT filtering i.archived, to stay in
                  -- exact parity with the Items list (listItems does not filter
                  -- it either). If archived items should be excluded from
                  -- portfolio value, add the SAME filter to listItems in the
                  -- same change so the card/footer/portfolio stay consistent.
                GROUP BY COALESCE(NULLIF(i.category, ''), 'uncategorized')
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


async def _compute_category_deep_dive(
    pool,
    category: str,
    days: int,
    currency: str,
    limit: int,
    offset: int,
    include_rankings: bool = False,
) -> CategoryDeepDiveResponse:
    """Heavy market_hits aggregation for a category deep-dive.

    Pure compute: no auth, no response cache, no demand-signal side effects.
    Shared by the HTTP endpoint and the background pre-warmer so the (slow,
    multi-million-row) query logic lives in exactly one place. Raises on DB
    error so callers can decide whether to return an empty payload or skip
    caching — it must never silently cache an error as an empty result.

    `include_rankings` gates the second, far heavier pass (top-traded /
    top-movers). It is off by default because no screen reads those fields —
    the category screen shows only avg price + the value sparkline, and market
    movers come from mv_market_top_movers. Skipping it roughly thirds the cold
    compute time (mtg: ~17s -> ~5s), keeping a cold miss under the client's
    20s timeout instead of racing it.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with pool.acquire() as conn:
            # ------- combined daily stats: avg price, volume, and overall avg -------
            # Single scan of market_hits instead of 3 separate queries.
            # Pre-2026-05-02 this used `created_at` but market_hits has
            # no created_at column — endpoint 500'd. COALESCE matches the
            # rest of the readers (legacy NULL observed_at → seen_at).
            # The cutoff filter on seen_at also enables partition prune.
            daily_rows = await conn.fetch(
                """
                SELECT
                    date_trunc('day', COALESCE(observed_at, seen_at))   AS day,
                    AVG(price) FILTER (WHERE price IS NOT NULL)         AS avg_price,
                    COUNT(*)                                            AS cnt,
                    SUM(COUNT(*)) OVER ()                               AS grand_count,
                    SUM(SUM(CASE WHEN price IS NOT NULL THEN price ELSE 0 END)) OVER ()
                        / NULLIF(SUM(COUNT(price)) OVER (), 0)         AS overall_avg
                FROM market_hits
                -- FIX: filter on the dedicated `category` column, not
                -- `normalized_key LIKE 'cat%'`. normalized_key is the bare item
                -- SLUG (e.g. 'dsc-197-scute-swarm') with NO category prefix, so
                -- the LIKE matched only items whose slug happened to start with
                -- the category name — missing ~97% of pokemon/mtg data (empty
                -- insights) AND doing a slow leading-LIKE scan. category= uses
                -- the (category, seen_at) partition index.
                WHERE category = $1
                  AND seen_at >= $2
                GROUP BY date_trunc('day', COALESCE(observed_at, seen_at))
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
            # Traded + movers are computed from SOLD comps only
            # (is_listing IS NOT TRUE) — the daily/avg/trend stats above keep
            # listings for a fuller discovery chart, but rankings must be
            # honest. Movers use a median-of-first-half vs median-of-second-half
            # split (robust to outliers / placeholder prices) instead of a raw
            # first-vs-last delta, which produced absurd swings (e.g. a single
            # €0.01 placeholder → -100%, a one-off mispriced listing → +387200%).
            # The half-split point is the midpoint of the requested window.
            # Skip this pass unless rankings are explicitly requested — it is a
            # second GROUP BY normalized_key with percentile_cont over the whole
            # window (~12s of mtg's ~17s), and nothing on the FE consumes its
            # output. When off, combo_rows stays empty and the builders below
            # naturally yield empty top_traded/top_movers lists.
            combo_rows = []
            if include_rankings:
              half = cutoff + (datetime.now(timezone.utc) - cutoff) / 2
              combo_rows = await conn.fetch(
                """
                WITH per_key AS (
                    SELECT
                        normalized_key,
                        COALESCE(MAX(title), normalized_key) AS name,
                        COUNT(*) AS trades,
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY price)
                            FILTER (WHERE price IS NOT NULL AND price >= 1
                                    AND COALESCE(observed_at, seen_at) <  $3) AS med_old,
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY price)
                            FILTER (WHERE price IS NOT NULL AND price >= 1
                                    AND COALESCE(observed_at, seen_at) >= $3) AS med_new,
                        COUNT(price) FILTER (WHERE price IS NOT NULL AND price >= 1
                                    AND COALESCE(observed_at, seen_at) <  $3) AS cnt_old,
                        COUNT(price) FILTER (WHERE price IS NOT NULL AND price >= 1
                                    AND COALESCE(observed_at, seen_at) >= $3) AS cnt_new
                    FROM market_hits
                    -- Same fix as the daily query: filter by category, not a
                    -- leading-LIKE on the slug-only normalized_key.
                    WHERE category = $1
                      AND seen_at >= $2
                      AND (is_listing IS NOT TRUE)
                    GROUP BY normalized_key
                ),
                ranked AS (
                    SELECT
                        normalized_key, name, trades, med_old, med_new, cnt_old, cnt_new,
                        CASE WHEN med_old > 0 AND cnt_old >= 2 AND cnt_new >= 2
                             THEN (med_new - med_old) / med_old
                             ELSE NULL
                        END AS change_pct,
                        ROW_NUMBER() OVER (ORDER BY trades DESC) AS trade_rank
                    FROM per_key
                ),
                mover_ranked AS (
                    SELECT *,
                        ROW_NUMBER() OVER (ORDER BY ABS(change_pct) DESC) AS mover_rank
                    FROM ranked
                    -- clamp to <=300%: anything larger is noise, not a real move
                    WHERE change_pct IS NOT NULL AND ABS(change_pct) <= 3.0
                )
                SELECT normalized_key, name, trades, change_pct, trade_rank,
                       NULL::bigint AS mover_rank
                FROM ranked WHERE trade_rank <= 10
                UNION ALL
                SELECT normalized_key, name, trades, change_pct, NULL::bigint AS trade_rank,
                       mover_rank
                FROM mover_ranked WHERE mover_rank <= 10
                """,
                category.lower(),
                cutoff,
                half,
            )

            top_traded_items = sorted(
                [
                    {
                        "item_id": row["normalized_key"],
                        "name": row["name"],
                        "trades": row["trades"],
                    }
                    for row in combo_rows
                    if row["trade_rank"] is not None and row["trade_rank"] <= 10
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
                    if row["mover_rank"] is not None and row["mover_rank"] <= 10
                ],
                key=lambda x: abs(x["change_pct"]),
                reverse=True,
            )

            return CategoryDeepDiveResponse(
                category=category,
                currency=currency,
                avg_market_price=round(avg_market_price, 2),
                value_distribution=value_distribution[offset:offset + limit],
                volume_trend=volume_trend[offset:offset + limit],
                top_traded_items=top_traded_items[offset:offset + limit],
                top_movers=top_movers[offset:offset + limit],
            )

    except Exception as e:
        logger.error(f"[deep-dive compute] {category}: {e}")
        raise


async def _record_category_view(category: str, user_id: str) -> None:
    """Best-effort `category_viewed` demand signal with geo enrichment.

    Spawned fire-and-forget on every authenticated deep-dive view. Swallows its
    own errors — it's analytics, never user-facing.
    """
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


@router.get("/categories/{category}/deep-dive", response_model=CategoryDeepDiveResponse)
async def get_category_deep_dive(
    category: str,
    days: int = Query(30, ge=7, le=365),
    currency: str = Query("EUR"),
    include_rankings: bool = Query(
        False,
        description="Also compute top-traded / top-movers (heavy second pass; "
        "off by default so a cold miss stays under the client timeout).",
    ),
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

    Served from a 6h cache. A cold miss runs a heavy market_hits aggregation
    (tens of seconds for high-volume categories like pokemon/mtg), which the
    background warmer keeps primed — see `warm_category_deep_dives`.
    """
    limit, offset = pagination

    # Record the category view on EVERY authenticated request, fire-and-forget
    # so it never adds latency. This used to run only on the cache-miss path
    # (below), but the background warmer keeps the cache hot, so real user views
    # almost always hit cache and `category_viewed` silently stopped firing.
    spawn_bg(_record_category_view(category, user_id), "category_view_signal")

    # Check cache. Key is case-normalised so the warmer (which reads category
    # from the DB) and this endpoint (which reads it from the URL) can never
    # miss each other on casing.
    cache_key = f"deepdive:{category.lower()}:{days}:{currency}:{limit}:{offset}:{int(include_rankings)}"
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

    try:
        result = await _compute_category_deep_dive(
            pool, category, days, currency, limit, offset, include_rankings
        )
    except Exception:
        # Already logged in the helper. Return an empty payload (uncached) so
        # the next request retries rather than serving a cached error.
        return CategoryDeepDiveResponse(
            category=category,
            currency=currency,
            avg_market_price=0.0,
            value_distribution=[],
            volume_trend=[],
            top_traded_items=[],
            top_movers=[],
        )

    cache_set(cache_key, result, ttl=_DEEPDIVE_CACHE_TTL)
    return result


# ---------------------------------------------------------------------------
# Background cache pre-warmer
# ---------------------------------------------------------------------------
# The deep-dive aggregation scans 1M+ market_hits rows for high-volume
# categories (e.g. pokemon ~1.3M rows/30d → ~30s cold). The FE calls the
# endpoint with a short timeout, so a cold miss silently shows an empty Market
# Insights panel. This task computes + caches the default-parameter deep-dive
# for the busiest categories on an interval shorter than the cache TTL, so real
# users always hit the warm path (~ms). Runs in-process (cache is per-process;
# there is no Redis), spawned from the startup hook in main.py.

# Match the FE's call shape (no days/currency/pagination overrides) so the warm
# writes the exact cache key the endpoint reads.
_WARM_DAYS = 30
_WARM_CURRENCY = "EUR"
_WARM_LIMIT, _WARM_OFFSET = 50, 0
_WARM_TOP_N = 15
_WARM_INTERVAL_SECONDS = 3 * 3600  # 3h < 6h TTL → cache never goes cold


async def warm_category_deep_dives() -> int:
    """Pre-compute + cache the deep-dive for the top-N busiest categories.

    Returns the number of categories warmed. Best-effort per category; one
    failure never aborts the rest. Sleeps briefly between categories so the
    heavy scans don't monopolise a DB connection or the event loop.
    """
    pool = get_db_pool()
    if not pool:
        return 0
    try:
        async with pool.acquire() as conn:
            cats = await conn.fetch(
                """
                SELECT category
                FROM market_hits
                WHERE seen_at >= now() - make_interval(days => $1)
                  AND category IS NOT NULL
                GROUP BY category
                ORDER BY count(*) DESC
                LIMIT $2
                """,
                _WARM_DAYS,
                _WARM_TOP_N,
            )
    except Exception as e:
        logger.warning("[deepdive warm] could not list top categories: %s", e)
        return 0

    warmed = 0
    for row in cats:
        category = row["category"]
        try:
            result = await _compute_category_deep_dive(
                pool, category, _WARM_DAYS, _WARM_CURRENCY, _WARM_LIMIT, _WARM_OFFSET
            )
            # Warm the exact key the FE reads: default params, rankings off (:0).
            cache_key = (
                f"deepdive:{category.lower()}:{_WARM_DAYS}:{_WARM_CURRENCY}:"
                f"{_WARM_LIMIT}:{_WARM_OFFSET}:0"
            )
            cache_set(cache_key, result, ttl=_DEEPDIVE_CACHE_TTL)
            warmed += 1
        except Exception as e:
            logger.warning("[deepdive warm] %s failed: %s", category, e)
        await asyncio.sleep(2)
    logger.info("[deepdive warm] warmed %d/%d categories", warmed, len(cats))
    return warmed


async def deep_dive_warm_loop() -> None:
    """Periodically refresh the deep-dive cache for busy categories.

    Waits briefly before the first run so the DB pool and bake orchestrator
    finish their (IO-heavy) startup before this adds its own heavy scans.
    """
    await asyncio.sleep(90)
    while True:
        try:
            await warm_category_deep_dives()
        except Exception as e:
            logger.warning("[deepdive warm] loop iteration failed: %s", e)
        await asyncio.sleep(_WARM_INTERVAL_SECONDS)
