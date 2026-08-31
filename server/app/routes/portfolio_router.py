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
                -- Every point must value the WHOLE collection, not just the
                -- items that happen to have a prediction that day.
                --
                -- This summed pp.q50 alone, so a hand-added item (no
                -- price_predictions row, value stored on the item) contributed
                -- 0 to the curve. Home derives its headline "COLLECTION VALUE",
                -- the chart, AND the change % from this series, while the Items
                -- tab sums every item — so the two screens disagreed for any
                -- account with >= 2 days of prediction history. Below that the
                -- len(points) < 2 fallback masked it, which is why it survived.
                --
                -- Items with no prediction have no history either, so their
                -- stored value is a constant baseline added to every day. That
                -- keeps the last point equal to /portfolio/overview's total,
                -- which is what makes the screens agree.
                -- Uses the same expression as every other value site — see
                -- "One valuation expression" in docs/ARCHITECTURE.md.
                -- Rewritten 2026-08-03. The previous version had two faults,
                -- both visible on one screenshot (headline EUR 8.070, the same
                -- account's breakdown EUR 55, and a curve claiming the user
                -- owned a just-added item since July):
                --
                -- 1. It summed pp.q50 for every prediction row generated that
                --    day, with NO per-item dedup, while /portfolio/overview and
                --    /portfolio/category-stats value each item ONCE via
                --    DISTINCT ON. Any item with more than one prediction in a
                --    day was counted repeatedly, so this endpoint drifted above
                --    its siblings. See "One valuation expression, or the screen
                --    contradicts itself" in docs/ARCHITECTURE.md — the rule is
                --    to grep the EXPRESSION, not the file.
                -- 2. price_predictions is CATALOG-wide history keyed by
                --    item_ref, and nothing tied it to when the user acquired
                --    the item. Adding an item retroactively injected its whole
                --    past price curve into the user's history, so a card bought
                --    today appeared in last week's portfolio value.
                --
                -- Now: walk a day grid, hold each item from the day it entered
                -- the collection (items.created_at), and value it with the last
                -- prediction known ON OR BEFORE that day, else its stored value
                -- — the same COALESCE chain the sibling endpoints use. The last
                -- point therefore equals /portfolio/overview's total, which is
                -- what keeps the screens agreeing.
                WITH days AS (
                    SELECT generate_series($2::date, CURRENT_DATE, INTERVAL '1 day')::date AS day
                ),
                owned AS (
                    SELECT
                        i.id,
                        i.canonical_ref,
                        i.created_at::date AS since,
                        -- Stored-value fallback. TWO prediction sources cover
                        -- different items: price_predictions is catalog-model
                        -- output joined by canonical_ref, quick_predictions is
                        -- per-item QuickScan output joined by item_id. Using
                        -- either alone zeroes the other group.
                        COALESCE(
                            (SELECT qp.q50_eur FROM quick_predictions qp
                              WHERE qp.item_id = i.id
                              ORDER BY qp.created_at DESC LIMIT 1),
                            i.predicted_price_eur,
                            i.estimated_value,
                            0
                        ) AS stored_value
                    FROM items i
                    WHERE i.user_id = $1 AND NOT i.archived
                ),
                -- One prediction per item per day (the last of that day), so a
                -- chatty valuation run cannot multiply an item's contribution.
                per_day AS (
                    SELECT DISTINCT ON (o.id, DATE(pp.generated_at))
                        o.id,
                        DATE(pp.generated_at) AS day,
                        pp.q50
                    FROM owned o
                    JOIN price_predictions pp ON pp.item_ref = o.canonical_ref
                    WHERE pp.generated_at >= $2
                    ORDER BY o.id, DATE(pp.generated_at), pp.generated_at DESC
                )
                SELECT
                    d.day AS day,
                    COALESCE(SUM(
                        COALESCE(
                            (SELECT p.q50 FROM per_day p
                              WHERE p.id = o.id AND p.day <= d.day
                              ORDER BY p.day DESC LIMIT 1),
                            o.stored_value
                        )
                    ), 0) AS total_value
                FROM days d
                LEFT JOIN owned o ON o.since <= d.day
                GROUP BY d.day
                ORDER BY d.day ASC
                """,
                user_id,
                since,
            )

            points = [
                {"t": row["day"].isoformat(), "v": round(float(row["total_value"]), 2)}
                for row in rows
            ]

            # The day grid always emits a row per day, so an empty portfolio
            # would now draw a flat line along zero instead of the honest "No
            # history yet" empty state the FE renders for an empty series.
            # Collapse an all-zero curve back to no points.
            if points and not any(p["v"] > 0 for p in points):
                points = []

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
                    -- One definition (Stage 2, 2026-08-19): the same
                    -- function v_item_values_v1 wraps. `latest` is no longer
                    -- needed for the value — the function does that join
                    -- itself — but it stays for the q10/q90 band elsewhere.
                    SELECT COALESCE(SUM(iv.value_eur), 0)
                    FROM items i
                    LEFT JOIN LATERAL public.item_value_v1(i) iv ON TRUE
                    WHERE i.user_id = $1 AND NOT i.archived
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
                    iv.value_eur AS current_value,
                    -- `prev_value` is deliberately NOT the function: it answers
                    -- "what was this worth BEFORE", and the function only knows
                    -- the current chain. Left as its own expression rather than
                    -- forced through a shared definition that does not mean the
                    -- same thing.
                    COALESCE(p.prev_q50, l.q50, i.predicted_price_eur, i.estimated_value, 0) AS prev_value
                FROM items i
                LEFT JOIN LATERAL public.item_value_v1(i) iv ON TRUE
                LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                LEFT JOIN prev p ON p.item_ref = i.canonical_ref
                WHERE i.user_id = $1 AND NOT i.archived
                ORDER BY iv.value_eur DESC
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
                -- PER-ITEM 7-DAY MOVE (added 2026-08-27).
                --
                -- The client has wanted this twice. "Movers" was deleted on
                -- 2026-08-14 and "Holdings" on 2026-08-26, both because they
                -- rendered `change_1d_pct`, which this endpoint has never
                -- returned — so the column was always undefined and the
                -- feature never drew a row. The answer both times was to
                -- delete the reader; the actual gap was that nothing COMPUTED
                -- the number.
                --
                -- It is computable: `price_predictions` keeps history, and
                -- measured 2026-08-27, 66,172 of 71,858 item_refs have
                -- predictions spanning >= 7 days. `change_7d_pct` on the
                -- CATEGORY endpoint is a different figure (a category total),
                -- so this is not a duplicate of it.
                --
                -- DISTINCT ON picks the newest prediction at or before the
                -- cutoff; an item with no prediction that old yields NULL, and
                -- NULL must reach the client as "unknown" rather than as 0% —
                -- a flat line and a missing measurement are not the same
                -- claim, which is the mistake `change_1d_pct` shipped.
                week_ago AS (
                    SELECT DISTINCT ON (pp.item_ref)
                        pp.item_ref, pp.q50 AS q50_7d
                    FROM price_predictions pp
                    JOIN items i ON i.canonical_ref = pp.item_ref
                    WHERE i.user_id = $1
                      AND pp.generated_at <= now() - interval '7 days'
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
                    -- Same fallback chain as /portfolio/overview (see the note
                    -- at its query): a model prediction if one exists, else the
                    -- item's own stored value. Overview was fixed for this and
                    -- this sibling was not, so the SAME portfolio read EUR 55
                    -- in the header and EUR 0 on every row -- verified on a
                    -- live account whose 3 items have zero price_predictions.
                    -- ONE DEFINITION (2026-08-19, Stage 2). `public.item_value_v1`
                    -- is the same function `v_item_values_v1` wraps, so this
                    -- endpoint and the app can no longer drift — they were
                    -- copies held in step by tests, and this chain had already
                    -- drifted twice.
                    --
                    -- Joined LATERALLY, never as `(item_value_v1(i)).value_eur`:
                    -- Postgres expands that form into one call PER FIELD, which
                    -- would double every subquery inside the function.
                    iv.value_eur AS current_value,
                    COALESCE(l.q10, 0) AS q10,
                    COALESCE(l.q90, 0) AS q90,
                    -- NULL, not 0, when there is no 7-day-old prediction to
                    -- compare against. See the week_ago CTE.
                    CASE WHEN w.q50_7d IS NOT NULL AND w.q50_7d > 0 AND l.q50 IS NOT NULL
                         THEN round(((l.q50 - w.q50_7d) / w.q50_7d)::numeric, 4)
                    END AS change_7d_pct,
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
                    -- Fees are added ONLY to a real purchase price (2026-08-31).
                    -- Adding them to the `first_q50` fallback would attach a
                    -- member's tax and postage to a MODEL ESTIMATE, which is
                    -- the drift-as-profit bug this COALESCE already exists to
                    -- flag -- made worse by a number that looks like evidence.
                    -- The CASE keeps the two branches honestly separate:
                    -- real basis + real fees, or an estimate on its own.
                    CASE WHEN i.purchase_price_eur IS NOT NULL
                         THEN i.purchase_price_eur + COALESCE(i.acquisition_fees_eur, 0)
                         ELSE COALESCE(e.first_q50, 0)
                    END AS cost_basis,
                    -- Which SIDE of that COALESCE was used. Without this the
                    -- client cannot tell profit from model drift: for an item
                    -- with no purchase price, cost_basis is the earliest
                    -- prediction, so unrealized_pl measures how far the MODEL
                    -- moved, not what the member made. Both arrive as a number
                    -- called "unrealized_pl" and look identical.
                    (i.purchase_price_eur IS NOT NULL) AS has_purchase_price,
                    -- Provenance from the SAME call, so the label can never
                    -- describe a number the caller did not use.
                    iv.value_source,
                    -- WHICH SET THIS ITEM BELONGS TO, AND HOW BIG THAT SET IS.
                    --
                    -- app/sets-to-complete.tsx has always mapped `collection`,
                    -- `collection_name`, `set_code` and `set_size` off this
                    -- response, and this SELECT returned none of them, so every
                    -- one read null. With no set size the client fell back to
                    -- "expected = what you own", every set computed as exactly
                    -- 100% complete, and its 0.4..0.95 band filtered all of them
                    -- away: the screen was empty for every account, always.
                    --
                    -- VOCABULARY: `sets.name` and `items.collection_name` are
                    -- the SAME STRING, and `sets.category_id` and `i.category`
                    -- are both SLUGS ('pokemon', not 'Pokemon'). Joining a slug
                    -- to a display name is how 44 joins matched nothing for four
                    -- months (learning_join_vocabulary_slug_vs_display_name), so
                    -- it is stated here rather than left to be rediscovered.
                    i.collection_name,
                    s.total_items AS set_size
                FROM items i
                LEFT JOIN LATERAL public.item_value_v1(i) iv ON TRUE
                LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                LEFT JOIN earliest e ON e.item_ref = i.canonical_ref
                -- LEFT: an item with no 7-day-old prediction keeps its row and
                -- gets a NULL move, rather than dropping out of the portfolio.
                LEFT JOIN week_ago w ON w.item_ref = i.canonical_ref
                -- LEFT, and case-insensitive: an item may name a set we hold no
                -- catalogue row for, and that item must still come back. It
                -- simply arrives with set_size NULL and counts toward nothing.
                LEFT JOIN public.sets s
                       ON s.category_id = i.category
                      AND lower(s.name) = lower(i.collection_name)
                WHERE i.user_id = $1 AND NOT i.archived
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
                    # False => unrealized_pl is model drift, not profit. Callers
                    # must not sum it into a headline P/L figure.
                    "has_purchase_price": bool(r["has_purchase_price"]),
                    # Which link produced current_value. 'user_estimate' /
                    # 'app_estimate' mean nobody checked the number, so a
                    # caller must not add it to a figure it calls "market
                    # value" — see docs/ARCHITECTURE.md value-sources.
                    "value_source": r["value_source"],
                    "q10": round(float(r["q10"] or 0), 2),
                    "q90": round(float(r["q90"] or 0), 2),
                    # None stays None. `float(x or 0)` here would turn "we have
                    # no 7-day-old prediction" into "this item moved 0.0%",
                    # which is a claim we cannot support — and is precisely the
                    # shape that made change_1d_pct useless twice over.
                    "change_7d_pct": (
                        float(r["change_7d_pct"])
                        if r["change_7d_pct"] is not None else None
                    ),
                    # Nullable on purpose, both of them. `null` means "this item
                    # names no set" / "we hold no catalogue row for that set" —
                    # which is NOT the same as a set of size 0, and the client
                    # must be able to tell those apart before it claims a
                    # completeness percentage (learning_empty_answer_rendered_as_zero).
                    "collection_name": r["collection_name"],
                    "set_size": int(r["set_size"]) if r["set_size"] is not None else None,
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
                    WHERE i.user_id = $1 AND NOT i.archived
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
                ),
                -- Same fallback chain as /portfolio/overview: a prediction if
                -- one exists, else the item's own stored value. Without it this
                -- endpoint reported total_value 0.00 for categories the header
                -- valued at EUR 55, because hand-added items have no
                -- price_predictions row. Both prediction tables are read, per
                -- docs/ARCHITECTURE.md "There are TWO prediction tables" —
                -- neither source dominates.
                -- COALESCE on category too: `category IS NOT NULL` silently
                -- dropped uncategorised items from every category breakdown,
                -- so the parts did not add up to the whole.
                --
                -- The chain deliberately does NOT end in 0 any more (2026-08-10).
                -- It used to, and `AVG` then counted every unpriced item as a
                -- EUR 0 sample IN THE DENOMINATOR. For the 40+ categories with
                -- no sold-comp source (watches, whiskey, lego, warhammer … see
                -- CLAUDE.md "catalog <-> price crosswalk", ~62,000 rows at 0%
                -- priced) that dragged the reported average to near zero —
                -- CLAUDE.md's `unknown-as-zero` class, rendering "unknown" as
                -- "nothing". NULL means "we do not know", and every aggregate
                -- below skips it. SUM and MAX are unchanged by this: they
                -- already ignored NULLs, so only the average was ever wrong.
                --
                -- The value is computed ONCE in `valued` instead of being
                -- copy-pasted into five aggregates — the old shape made it
                -- possible for one copy to drift from the others.
                valued AS (
                    SELECT
                        COALESCE(NULLIF(i.category, ''), 'uncategorized') AS category,
                        COALESCE(
                            l.q50,
                            (SELECT qp.q50_eur FROM quick_predictions qp
                              WHERE qp.item_id = i.id
                              ORDER BY qp.created_at DESC LIMIT 1),
                            i.predicted_price_eur,
                            i.estimated_value
                        ) AS value_eur,
                        p.q50_7d
                    FROM items i
                    LEFT JOIN latest l ON l.item_ref = i.canonical_ref
                    LEFT JOIN prev_7d p ON p.item_ref = i.canonical_ref
                    WHERE i.user_id = $1 AND NOT i.archived
                )
                -- Median, not mean. In a category where prices are genuinely
                -- dispersed — a EUR 40 Seiko beside a EUR 18,000 Daytona — the
                -- mean describes neither item. The median names a real middle,
                -- and min/max carry the spread the mean was hiding.
                SELECT
                    category,
                    COUNT(*) AS item_count,
                    COUNT(value_eur) AS priced_count,
                    COALESCE(SUM(value_eur), 0) AS total_value,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value_eur) AS median_value,
                    MIN(value_eur) AS min_item_value,
                    MAX(value_eur) AS max_item_value,
                    COALESCE(SUM(value_eur), 0) - COALESCE(SUM(q50_7d), 0) AS change_7d
                FROM valued
                GROUP BY category
                ORDER BY total_value DESC
                """,
                user_id,
            )

            categories = []
            for r in rows:
                tv = float(r["total_value"] or 0)
                c7 = float(r["change_7d"] or 0)
                trend = "up" if c7 > 0 else ("down" if c7 < 0 else "flat")
                # `median_value` / `min_item_value` are None for a category where
                # NOTHING is priced. Emitted as null, NOT 0.0 — a category we
                # cannot value must not claim to be worth nothing, which is the
                # whole point of the SQL change above. The client renders the
                # spread only when it has one.
                med = r["median_value"]
                lo = r["min_item_value"]
                hi = r["max_item_value"]
                categories.append({
                    "category": r["category"],
                    "item_count": int(r["item_count"]),
                    "priced_count": int(r["priced_count"]),
                    "total_value": round(tv, 2),
                    "median_value": round(float(med), 2) if med is not None else None,
                    "min_item_value": round(float(lo), 2) if lo is not None else None,
                    "max_item_value": round(float(hi), 2) if hi is not None else None,
                    "change_7d": round(c7, 2),
                    "change_7d_pct": round(c7 / tv * 100, 2) if tv > 0 else 0.0,
                    "trend": trend,
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
                    WHERE user_id = $1 AND category IS NOT NULL AND NOT archived
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
                    WHERE category = $1 AND NOT archived
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
                    WHERE i.category IS NOT NULL AND NOT i.archived
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


@router.get(
    "/portfolio/realised-pl",
    summary="Realised profit and loss on items actually sold",
)
async def realised_pl(user_id: str = Depends(get_current_user_id)):
    """What a member ACTUALLY made, after every fee on both sides.

    docs/COLLECTOR_DEMAND.md §5 is the whole reason this exists: collectors
    track prices and not their true cost basis, and the worked example is a
    EUR 956.25 card sold for EUR 1000 that looks like a EUR 44 profit and is a
    EUR 104 LOSS once the platform fee and postage land. Nothing in this app
    could show that -- `unrealized_pl` is a projection against a live estimate,
    and `useListForSale` computes a net BEFORE a sale, not after one.

    Both halves already existed and had never been joined:

      * SELL side -- `marketplace_sales` stores `net_proceeds`, computed at
        marketplace_listing_router.py:983 as
        `sale_price - platform_fee - payment_processing_fee - shipping_cost_actual`.
      * BUY side -- `items.purchase_price_eur` plus `acquisition_fees_eur`,
        added 2026-08-31; before that the basis was the sticker price and every
        gain was overstated.

    ⚠️ `cost_basis_known` is returned per row and is NOT decoration. A sale
    whose item has no recorded purchase price has NO basis, and subtracting
    zero would render the entire net proceeds as pure profit -- the
    `None or 0` failure that turns UNKNOWN into a confident number
    (learning_a_blind_source_deletes_the_finding_not_just_the_number). Those
    rows carry `profit: null` and are summed separately, never into `total`.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id,
                       s.sold_at,
                       s.sale_price,
                       s.currency,
                       s.net_proceeds,
                       s.platform_fee,
                       s.payment_processing_fee,
                       s.shipping_cost_actual,
                       i.id       AS item_id,
                       i.name     AS item_name,
                       i.category,
                       i.purchase_price_eur,
                       i.acquisition_fees_eur,
                       -- Mirrors the CASE in /portfolio/items exactly. Two
                       -- endpoints answering "what did you pay" must not drift.
                       CASE WHEN i.purchase_price_eur IS NOT NULL
                            THEN i.purchase_price_eur + COALESCE(i.acquisition_fees_eur, 0)
                       END AS cost_basis
                  FROM marketplace_sales s
                  JOIN marketplace_listings l ON l.id = s.listing_id
                  LEFT JOIN items i ON i.id = l.item_id
                 WHERE s.user_id = $1::uuid
                 ORDER BY s.sold_at DESC
                 LIMIT 200
                """,
                user_id,
            )

        return summarise_realised_sales(rows)
    except Exception as e:
        _logger.error("[portfolio/realised-pl] DB error: %s", e)
        raise error_response(500, "Failed to load realised P/L", code="DB_ERROR")


def summarise_realised_sales(rows) -> dict:
    """Turn sale rows into the P/L payload. Pure -- no I/O, so it is TESTABLE.

    Split out deliberately: a test that reimplements this loop pins nothing.
    Proven the hard way on 2026-08-30, when the observed_at tests copied the
    writer's row-building into the test file and stayed green while the fix was
    reverted (learning_tests_that_pin_a_stub).
    """
    sales = []
    total_profit = 0.0
    total_proceeds = 0.0
    unknown_basis = 0
    for r in rows:
        basis = float(r["cost_basis"]) if r["cost_basis"] is not None else None
        net = float(r["net_proceeds"]) if r["net_proceeds"] is not None else None
        # Rounded HERE, not just in the totals: an unrounded per-sale figure
        # reaches the client as -104.04999999999995 and renders that way.
        profit = round(net - basis, 2) if (basis is not None and net is not None) else None
        if profit is None:
            unknown_basis += 1
        else:
            total_profit += profit
        if net is not None:
            total_proceeds += net
        sales.append({
            "id": str(r["id"]),
            "item_id": str(r["item_id"]) if r["item_id"] else None,
            "item_name": r["item_name"],
            "category": r["category"],
            "sold_at": r["sold_at"].isoformat() if r["sold_at"] else None,
            "sale_price": float(r["sale_price"]) if r["sale_price"] is not None else None,
            "currency": r["currency"],
            "net_proceeds": net,
            "cost_basis": basis,
            "cost_basis_known": basis is not None,
            "profit": profit,
            "fees": {
                "platform": float(r["platform_fee"] or 0),
                "payment_processing": float(r["payment_processing_fee"] or 0),
                "shipping": float(r["shipping_cost_actual"] or 0),
            },
        })

    return {
        "sales": sales,
        "count": len(sales),
        # `total_profit` covers ONLY the rows with a known basis. Stating how
        # many were excluded is the difference between a total and a total that
        # quietly under-counts.
        "total_profit": round(total_profit, 2),
        "total_net_proceeds": round(total_proceeds, 2),
        "sales_without_cost_basis": unknown_basis,
    }
