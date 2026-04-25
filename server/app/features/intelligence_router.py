"""
Intelligence router — queryable demand-side surface.

Surfaces aggregations over every demand input we record so admin/ops can see
what users want, follow, and engage with. No new schema — all queries hit
existing tables (demand_signals, watchlist_items, event_follows_v1, etc.).

Pairs with the supply-side queries already in data_moat (/data-moat/*). Together
the two routers expose every leg of the supply/demand intelligence loop.

Endpoints:
- GET /intelligence/top-searches            — most-searched query texts
- GET /intelligence/top-watchlists          — most-watchlisted items
- GET /intelligence/top-followed-events     — most-followed events
- GET /intelligence/top-followed-categories — most-followed categories
- GET /intelligence/top-active-threads      — chat threads with most members
- GET /intelligence/top-viewed-items        — proxy for mv_demand_heat
- GET /intelligence/health                  — single-shot freshness/count snapshot
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])

_intel_limit = per_user_rate_limit(30, window_seconds=60, scope="intelligence")


@router.get("/top-searches")
async def top_searches(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = Query(None, max_length=64),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-searched query texts, with unique-user counts and last-seen times."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    cat_filter = "AND category = $3" if category else ""
    params: list = [days, limit] + ([category] if category else [])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                lower(trim(query_text)) AS query,
                COALESCE(category, 'unspecified') AS category,
                COUNT(*) AS searches,
                COUNT(DISTINCT user_id) AS unique_users,
                MAX(created_at) AS last_seen_at
            FROM public.demand_signals
            WHERE signal_type = 'search_query'
              AND query_text IS NOT NULL
              AND length(trim(query_text)) > 0
              AND created_at >= now() - ($1 || ' days')::interval
              {cat_filter}
            GROUP BY 1, 2
            ORDER BY searches DESC, unique_users DESC
            LIMIT $2
            """,
            *params,
        )
    return {
        "days": days,
        "category": category,
        "items": [
            {
                "query": r["query"],
                "category": r["category"],
                "searches": r["searches"],
                "unique_users": r["unique_users"],
                "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-watchlists")
async def top_watchlists(
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = Query(None, max_length=64),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-watchlisted items across all users (current state, not historical)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    cat_filter = "AND category = $2" if category else ""
    params: list = [limit] + ([category] if category else [])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                COALESCE(item_id, title) AS item_ref,
                title,
                COALESCE(category, 'unspecified') AS category,
                COUNT(*) AS watchers,
                COUNT(DISTINCT user_id) AS unique_users,
                AVG(target_price) FILTER (WHERE target_price IS NOT NULL) AS avg_target_price,
                MIN(target_price) FILTER (WHERE target_price IS NOT NULL) AS min_target_price,
                MAX(created_at) AS last_added_at
            FROM public.watchlist_items
            WHERE TRUE
              {cat_filter}
            GROUP BY 1, 2, 3
            ORDER BY unique_users DESC, watchers DESC
            LIMIT $1
            """,
            *params,
        )
    return {
        "category": category,
        "items": [
            {
                "item_ref": r["item_ref"],
                "title": r["title"],
                "category": r["category"],
                "watchers": r["watchers"],
                "unique_users": r["unique_users"],
                "avg_target_price": float(r["avg_target_price"]) if r["avg_target_price"] is not None else None,
                "min_target_price": float(r["min_target_price"]) if r["min_target_price"] is not None else None,
                "last_added_at": r["last_added_at"].isoformat() if r["last_added_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-followed-events")
async def top_followed_events(
    limit: int = Query(50, ge=1, le=500),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-followed events / canonical refs (from event_follows_v1)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                canonical_key,
                category,
                COUNT(DISTINCT user_id) AS followers,
                MAX(created_at) AS last_followed_at
            FROM public.event_follows_v1
            WHERE enabled IS NOT FALSE
            GROUP BY canonical_key, category
            ORDER BY followers DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "items": [
            {
                "canonical_key": r["canonical_key"],
                "category": r["category"],
                "followers": r["followers"],
                "last_followed_at": r["last_followed_at"].isoformat() if r["last_followed_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-followed-categories")
async def top_followed_categories(
    limit: int = Query(60, ge=1, le=200),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-followed categories (from user_category_follows)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                category_id,
                COUNT(DISTINCT user_id) AS followers,
                MAX(created_at) AS last_followed_at
            FROM public.user_category_follows
            GROUP BY category_id
            ORDER BY followers DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "items": [
            {
                "category": r["category_id"],
                "followers": r["followers"],
                "last_followed_at": r["last_followed_at"].isoformat() if r["last_followed_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-active-threads")
async def top_active_threads(
    limit: int = Query(30, ge=1, le=200),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-active chat threads (member count + last message)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id AS thread_id,
                t.kind,
                t.category,
                COUNT(DISTINCT m.user_id) AS members,
                MAX(t.updated_at) AS updated_at,
                MAX(t.created_at) AS created_at
            FROM public.chat_threads_v1 t
            LEFT JOIN public.chat_thread_members_v1 m ON m.thread_id = t.id
            GROUP BY t.id, t.kind, t.category
            ORDER BY members DESC, updated_at DESC NULLS LAST
            LIMIT $1
            """,
            limit,
        )
    return {
        "items": [
            {
                "thread_id": str(r["thread_id"]),
                "kind": r["kind"],
                "category": r["category"],
                "members": r["members"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-viewed-items")
async def top_viewed_items(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = Query(None, max_length=64),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-viewed items by demand_signals (item_viewed/item_scanned)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    cat_filter = "AND category = $3" if category else ""
    params: list = [days, limit] + ([category] if category else [])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                COALESCE(category, 'unspecified') AS category,
                item_key,
                COUNT(*) FILTER (WHERE signal_type = 'item_viewed') AS views,
                COUNT(*) FILTER (WHERE signal_type = 'item_scanned') AS scans,
                COUNT(DISTINCT user_id) AS unique_users,
                MAX(created_at) AS last_signal_at
            FROM public.demand_signals
            WHERE signal_type IN ('item_viewed', 'item_scanned')
              AND item_key IS NOT NULL
              AND created_at >= now() - ($1 || ' days')::interval
              {cat_filter}
            GROUP BY 1, 2
            ORDER BY (COUNT(*)) DESC, unique_users DESC
            LIMIT $2
            """,
            *params,
        )
    return {
        "days": days,
        "category": category,
        "items": [
            {
                "category": r["category"],
                "item_key": r["item_key"],
                "views": r["views"],
                "scans": r["scans"],
                "unique_users": r["unique_users"],
                "last_signal_at": r["last_signal_at"].isoformat() if r["last_signal_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-events")
async def top_events(
    days: int = Query(14, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-engaged events: combines event_viewed signals + follows + RSVPs.

    Without this you can only see followers (a thin signal). Most events get
    viewed many more times than followed; ranking by combined engagement
    surfaces what's actually drawing attention.
    """
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH views AS (
                SELECT item_key AS event_id,
                       COUNT(*) AS view_count,
                       COUNT(DISTINCT user_id) AS unique_viewers
                FROM public.demand_signals
                WHERE signal_type = 'event_viewed'
                  AND item_key IS NOT NULL
                  AND created_at >= now() - ($1 || ' days')::interval
                GROUP BY item_key
            ),
            follows AS (
                SELECT canonical_key AS event_id,
                       COUNT(DISTINCT user_id) AS follower_count
                FROM public.event_follows_v1
                WHERE enabled IS NOT FALSE
                GROUP BY canonical_key
            ),
            rsvps AS (
                SELECT event_id::text AS event_id,
                       COUNT(*) AS rsvp_count
                FROM public.event_attendees
                GROUP BY event_id
            )
            SELECT
                e.id::text AS event_id,
                e.title,
                e.category_id,
                e.starts_at,
                COALESCE(v.view_count, 0) AS views,
                COALESCE(v.unique_viewers, 0) AS unique_viewers,
                COALESCE(f.follower_count, 0) AS followers,
                COALESCE(r.rsvp_count, 0) AS rsvps,
                COALESCE(v.view_count, 0)
                  + 5 * COALESCE(f.follower_count, 0)
                  + 10 * COALESCE(r.rsvp_count, 0) AS engagement_score
            FROM public.events e
            LEFT JOIN views v ON v.event_id = e.id::text
            LEFT JOIN follows f ON f.event_id = e.canonical_key
            LEFT JOIN rsvps r ON r.event_id = e.id::text
            WHERE COALESCE(v.view_count, 0)
                + COALESCE(f.follower_count, 0)
                + COALESCE(r.rsvp_count, 0) > 0
            ORDER BY engagement_score DESC
            LIMIT $2
            """,
            days, limit,
        )
    return {
        "days": days,
        "items": [
            {
                "event_id": r["event_id"],
                "title": r["title"],
                "category_id": r["category_id"],
                "starts_at": r["starts_at"].isoformat() if r["starts_at"] else None,
                "views": r["views"],
                "unique_viewers": r["unique_viewers"],
                "followers": r["followers"],
                "rsvps": r["rsvps"],
                "engagement_score": r["engagement_score"],
            }
            for r in rows
        ],
    }


@router.get("/top-affiliates")
async def top_affiliates(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(50, ge=1, le=500),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Most-clicked affiliate-link sources + queries.

    Reads `demand_signals` where signal_type = 'affiliate_click'. Source is
    encoded in `item_key` (or its prefix), query in `query_text`. Use this
    to see which marketplaces actually convert and which queries are
    bouncing users out of the app.
    """
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                COALESCE(item_key, 'unknown') AS source,
                COALESCE(category, 'unspecified') AS category,
                COUNT(*) AS clicks,
                COUNT(DISTINCT user_id) AS unique_users,
                MAX(created_at) AS last_click_at
            FROM public.demand_signals
            WHERE signal_type = 'affiliate_click'
              AND created_at >= now() - ($1 || ' days')::interval
            GROUP BY 1, 2
            ORDER BY clicks DESC
            LIMIT $2
            """,
            days, limit,
        )
    return {
        "days": days,
        "items": [
            {
                "source": r["source"],
                "category": r["category"],
                "clicks": r["clicks"],
                "unique_users": r["unique_users"],
                "last_click_at": r["last_click_at"].isoformat() if r["last_click_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/top-chat-connections")
async def top_chat_connections(
    limit: int = Query(30, ge=1, le=200),
    _user: str = Depends(get_current_user_id),
    _rl=Depends(_intel_limit),
):
    """Users with the most chat connections (members + DM partners).

    Surfaces high-connector users who often drive community formation.
    Useful for moderation prioritisation + super-user identification.
    """
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                user_id,
                COUNT(DISTINCT thread_id) AS thread_count,
                MAX(created_at) AS last_joined_at
            FROM public.chat_thread_members_v1
            GROUP BY user_id
            ORDER BY thread_count DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "items": [
            {
                "user_id": str(r["user_id"]),
                "thread_count": r["thread_count"],
                "last_joined_at": r["last_joined_at"].isoformat() if r["last_joined_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/health")
async def intelligence_health(
    _user: str = Depends(get_current_user_id),
):
    """One-shot snapshot of every demand-side input table.

    Surfaces row counts + most-recent write per source so a dead loop is
    obvious without a per-source query. Pair with /data-moat/health for the
    supply side.
    """
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="no_db_pool")

    sources: list[dict] = []
    src_specs = [
        ("demand_signals", "created_at"),
        ("watchlist_items", "created_at"),
        ("event_follows_v1", "created_at"),
        ("user_category_follows", "created_at"),
        ("chat_threads_v1", "created_at"),
        ("chat_thread_members_v1", "created_at"),
        ("notification_impressions", "first_seen_at"),
        ("notification_interactions", "occurred_at"),
        ("notification_outcomes", "acted_at"),
        ("price_ground_truths", "recorded_at"),
        ("user_feedback_events_v1", "created_at"),
        ("predict_sessions", "created_at"),
        ("label_events", "created_at"),
    ]
    async with pool.acquire() as conn:
        for table, ts_col in src_specs:
            try:
                row = await conn.fetchrow(
                    f"SELECT COUNT(*) AS c, MAX({ts_col}) AS latest FROM public.{table}"
                )
                sources.append({
                    "source": table,
                    "rows": int(row["c"] or 0),
                    "latest": row["latest"].isoformat() if row["latest"] else None,
                })
            except Exception as e:
                sources.append({"source": table, "error": str(e)[:80]})
    return {"sources": sources}
