"""
Social router — block/unblock users + user search.

Endpoints:
- GET    /social/users/search?q=...&limit=20 — Search users by name/handle
- POST   /social/block/{user_id}   — Block a user
- DELETE /social/block/{user_id}   — Unblock a user
- GET    /social/blocked           — List blocked users
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/social", tags=["Social"])
logger = logging.getLogger(__name__)

# Per-user: 30 search requests per minute (expensive DB queries)
_social_search_limit = per_user_rate_limit(30, window_seconds=60, scope="social_search")
_social_write_limit = per_user_rate_limit(20, window_seconds=60, scope="social_write")


# ── Response Models ──────────────────────────────────────────────────────────


class BlockResponse(BaseModel):
    success: bool
    message: str


class BlockedUserItem(BaseModel):
    user_id: str
    blocked_at: str


class BlockedListResponse(BaseModel):
    blocked: list[BlockedUserItem]


class UserSearchItem(BaseModel):
    id: str
    display_name: str
    handle: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_color: Optional[str] = None


class UserSearchResponse(BaseModel):
    users: list[UserSearchItem]


class CategoryLeaderboardItem(BaseModel):
    rank: int
    user_id: str
    display_name: str
    handle: Optional[str] = None
    avatar_url: Optional[str] = None
    item_count: int
    value_eur: float = 0.0
    # How much of this member's collection in this category is DOCUMENTED —
    # a photo, a condition and a purchase price on the same item. Added
    # 2026-08-19 as the second axis for categories that cannot be ranked by
    # value: 40+ categories have no sold-comp source, so a value board there is
    # every member at 0.00.
    #
    # It is also the only leaderboard metric that pays the platform back. Item
    # COUNT rewards adding rows; documented % rewards adding the photos and
    # purchase prices that the catalogue and the comp gap are starved of.
    documented_count: int = 0
    documented_pct: float = 0.0
    is_you: bool = False


class CategoryLeaderboardResponse(BaseModel):
    category: str
    metric: str
    leaderboard: list[CategoryLeaderboardItem]
    your_rank: Optional[int] = None
    total_ranked: int = 0
    # FALSE => nobody on this board has a single comp-backed item, so ranking
    # by value would sort a column of zeros and present it as a standing.
    #
    # MEASURED, not a hardcoded category list: a category that gains a price
    # source starts offering the value board by itself, and one that loses it
    # stops — the same self-healing property that made deriving the catalogue
    # from the price source the right call (CLAUDE.md, the crosswalk section).
    value_ranking_available: bool = True


class CollectorCategoryStanding(BaseModel):
    """One category a collector holds, and where they stand in it.

    `rank` / `total_ranked` are Optional and mean "not ranked here", which is a
    real state and NOT the same as last place: a member who hides their item
    count is excluded from the board while still owning the items. Rendering a
    null as 0 or as "#—" of a total would state a placement the server refused
    to compute (see learning_empty_answer_rendered_as_zero).
    """

    category_id: str
    item_count: int
    value_eur: float = 0.0
    rank: Optional[int] = None
    total_ranked: Optional[int] = None


class CollectorCategoriesResponse(BaseModel):
    user_id: str
    categories: list[CollectorCategoryStanding]
    # False when the viewer may see the categories but not the money. The FE
    # needs to tell "worth nothing" apart from "not allowed to say".
    value_visible: bool = True


# ── User Search ──────────────────────────────────────────────────────────────


@router.get("/users/search", response_model=UserSearchResponse)
async def search_users(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    current_user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_social_search_limit),
):
    """
    Search users by display_name or handle (case-insensitive).
    Returns up to `limit` matching public profiles.
    """
    pool = get_db_pool()
    if pool is None:
        return UserSearchResponse(users=[])

    search_pattern = f"%{q}%"

    try:
        async with pool.acquire() as conn:
            # user_public_profiles has no avatar_color column; default
            # to NULL so the FE falls back to its tinted-initials placeholder.
            rows = await conn.fetch(
                """
                SELECT
                    user_id,
                    display_name,
                    handle,
                    avatar_url,
                    NULL::text AS avatar_color
                FROM user_public_profiles
                WHERE (
                    display_name ILIKE $1
                    OR handle ILIKE $1
                )
                AND user_id != $2::uuid
                ORDER BY
                    CASE
                        WHEN display_name ILIKE $3 THEN 0
                        WHEN handle ILIKE $3 THEN 1
                        ELSE 2
                    END,
                    display_name
                LIMIT $4
                """,
                search_pattern,
                current_user_id,
                f"{q}%",  # Prefix match ranks higher
                limit,
            )

        users = [
            UserSearchItem(
                id=str(row["user_id"]),
                display_name=row["display_name"] or "Unknown",
                handle=row["handle"],
                avatar_url=row["avatar_url"],
                avatar_color=row.get("avatar_color"),
            )
            for row in rows
        ]

        logger.info(
            "[social/search] q=%r user=%s results=%d",
            q, current_user_id, len(users),
        )
        return UserSearchResponse(users=users)

    except asyncpg.PostgresError as e:
        logger.error("[social/search] DB error: %s", e)
        raise error_response(500, "User search failed", code="DB_ERROR")


@router.post("/block/{user_id}", response_model=BlockResponse)
async def block_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_social_write_limit),
):
    """
    Block a user. Also auto-declines any pending DM threads between the pair.
    """
    # Validate UUID
    try:
        target_uuid = UUID(user_id)
    except ValueError:
        raise error_response(400, "Invalid user_id format", code="VALIDATION_ERROR")

    if str(target_uuid) == current_user_id:
        raise error_response(400, "Cannot block yourself", code="VALIDATION_ERROR")

    pool = get_db_pool()
    if pool is None:
        logger.info("[social/block] Offline mode: blocked user=%s", user_id)
        return BlockResponse(success=True, message="User blocked (offline mode)")

    try:
        async with pool.acquire() as conn:
            # Insert block (ignore if already exists)
            await conn.execute(
                """
                INSERT INTO user_blocks (blocker_id, blocked_id)
                VALUES ($1::uuid, $2::uuid)
                ON CONFLICT (blocker_id, blocked_id) DO NOTHING
                """,
                current_user_id,
                str(target_uuid),
            )

            # Auto-decline pending DM threads between these users
            await conn.execute(
                """
                UPDATE dm_threads
                SET status = 'declined'
                WHERE status = 'pending'
                  AND (
                    (requester_id = $1::uuid AND responder_id = $2::uuid) OR
                    (requester_id = $2::uuid AND responder_id = $1::uuid)
                  )
                """,
                current_user_id,
                str(target_uuid),
            )

        logger.info("[social/block] User %s blocked %s", current_user_id, user_id)
        return BlockResponse(success=True, message="User blocked")

    except asyncpg.PostgresError as e:
        logger.error("[social/block] DB error: %s", e)
        raise error_response(500, "Failed to block user", code="DB_ERROR")


@router.delete("/block/{user_id}", response_model=BlockResponse)
async def unblock_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_social_write_limit),
):
    """Unblock a user."""
    try:
        target_uuid = UUID(user_id)
    except ValueError:
        raise error_response(400, "Invalid user_id format", code="VALIDATION_ERROR")

    pool = get_db_pool()
    if pool is None:
        logger.info("[social/unblock] Offline mode: unblocked user=%s", user_id)
        return BlockResponse(success=True, message="User unblocked (offline mode)")

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM user_blocks
                WHERE blocker_id = $1::uuid AND blocked_id = $2::uuid
                """,
                current_user_id,
                str(target_uuid),
            )

        logger.info("[social/unblock] User %s unblocked %s", current_user_id, user_id)
        return BlockResponse(success=True, message="User unblocked")

    except asyncpg.PostgresError as e:
        logger.error("[social/unblock] DB error: %s", e)
        raise error_response(500, "Failed to unblock user", code="DB_ERROR")


@router.get("/blocked", response_model=BlockedListResponse)
async def list_blocked(
    current_user_id: str = Depends(get_current_user_id),
):
    """List all users blocked by the current user."""
    pool = get_db_pool()
    if pool is None:
        return BlockedListResponse(blocked=[])

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT blocked_id, created_at
                FROM user_blocks
                WHERE blocker_id = $1::uuid
                ORDER BY created_at DESC
                """,
                current_user_id,
            )

        blocked = [
            BlockedUserItem(
                user_id=str(row["blocked_id"]),
                blocked_at=row["created_at"].isoformat() if row["created_at"] else "",
            )
            for row in rows
        ]
        return BlockedListResponse(blocked=blocked)

    except asyncpg.PostgresError as e:
        logger.error("[social/blocked] DB error: %s", e)
        return BlockedListResponse(blocked=[])


# ── Category leaderboard ─────────────────────────────────────────────────────
#
# NOT the XP leaderboard. `GET /gamification/leaderboard` ranks by
# user_gamification.xp, which has no category dimension at all — and the XP UI
# is gated off (GAMIFICATION_UI_ENABLED = false) because the number is not
# meaningful. A per-category board therefore has to rank on something real, so
# this counts the items a member actually owns in the category.
#
# PRIVACY IS THE WHOLE DESIGN HERE. Settings → Privacy has "Allow discovery"
# and "Show item count", and the help text promises both do something. So:
#   - the base is `user_public_profiles`, which already excludes members who
#     turned discovery off;
#   - and anyone with show_item_count = false is excluded outright, because a
#     board of item counts is exactly the disclosure that switch refuses.
# Missing privacy rows default to TRUE, matching the table defaults and the FE.


@router.get("/leaderboard/category/{category_id}", response_model=CategoryLeaderboardResponse)
async def get_category_leaderboard(
    category_id: str,
    metric: str = Query("items", pattern="^(items|value|documented)$"),
    limit: int = Query(25, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_social_search_limit),
):
    """Top collectors in one category, ranked by items owned or by value held.

    `metric=value` is a STRICTER board than `metric=items`: it additionally
    excludes anyone with "Show collection value" off, because that is precisely
    the disclosure the switch refuses. Expect fewer rows, and do not pad it.
    """
    pool = get_db_pool()
    if pool is None:
        return CategoryLeaderboardResponse(
            category=category_id, metric=metric, leaderboard=[], total_ranked=0
        )

    try:
        async with pool.acquire() as conn:
            # The value expression must match `public.v_item_values_v1`, which
            # is the app's canonical definition, STEP FOR STEP:
            #
            #   quick_predictions.q50_eur (latest by created_at)
            #   -> price_predictions.q50 via items.canonical_ref (latest by
            #      generated_at)
            #   -> items.predicted_price_eur
            #   -> items.estimated_value
            #   -> 0
            #
            # It is re-written here rather than selected FROM the view because
            # the view carries `WHERE user_id = auth.uid()` — it answers "what
            # is MY collection worth" and cannot aggregate across members. That
            # duplication is exactly why the second step went missing on
            # 2026-08-16 and why `server/tests/test_leaderboard_value_parity.py`
            # now diffs this query against the view per user. Change one, change
            # both, and run that test.
            #
            # `npm run check:item-value-source` does NOT cover this: it checks
            # the FE provider and mapItemRow, and cannot see SQL in a Python
            # string (learning_sql_in_a_python_string_is_invisible_to_js_checkers).
            #
            # `metric` is interpolated, never parameterised, because ORDER BY
            # takes an expression and not a bind value — so both branches are
            # fixed literals chosen by an already-regex-validated key.
            # EACH BRANCH CARRIES ITS OWN DIRECTIONS, and the template below
            # does NOT append `DESC`.
            #
            # It used to, and the multi-column branch was silently inverted:
            # `ORDER BY documented_pct, documented_count DESC` applies DESC to
            # the LAST column only, so the percentage sorted ASCENDING and the
            # least-documented member ranked #1. Proven on prod against a
            # synthetic three-row set — 90% ranked #3, 10% ranked #1 — and
            # invisible in the live board because every member is at 0%
            # today.
            #
            # Ranked on the SHARE, not the count, so a member with 8 of 10
            # documented outranks one with 20 of 400. Ties break on the count,
            # otherwise a single perfectly-documented item tops the board.
            order_expr = (
                "total_value DESC" if metric == "value"
                else "documented_pct DESC, documented_count DESC" if metric == "documented"
                else "item_count DESC"
            )
            value_gate = (
                "AND COALESCE(ps.show_collection_value, TRUE) IS TRUE"
                if metric == "value"
                else ""
            )
            rows = await conn.fetch(
                f"""
                WITH base AS (
                    SELECT
                        p.user_id,
                        p.display_name,
                        p.handle,
                        p.avatar_url,
                        COUNT(i.id) AS item_count,
                        -- DOCUMENTED: a photo, a condition AND a purchase
                        -- price on the same item. All three, deliberately —
                        -- partial credit per field makes the bar ambiguous and
                        -- rewards half-filling every row rather than
                        -- completing any.
                        --
                        -- `condition` OR `condition_grade`: the two halves of
                        -- the same idea, written by different screens (the CSV
                        -- importer maps `grade` to condition_grade; add-manual
                        -- writes both). Requiring one specific column would
                        -- score identical collections differently depending on
                        -- how they were entered.
                        COUNT(i.id) FILTER (
                            WHERE NULLIF(btrim(i.image_url), '') IS NOT NULL
                              AND (NULLIF(btrim(i.condition), '') IS NOT NULL
                                   OR NULLIF(btrim(i.condition_grade), '') IS NOT NULL)
                              AND i.purchase_price_eur IS NOT NULL
                        ) AS documented_count,
                        -- MARKET TRUTH ONLY (2026-08-19). This is the one
                        -- number in the app that ranks members against each
                        -- other in public, so it may not rest on anything a
                        -- member typed about their own collection.
                        --
                        -- The chain stops after the two comp/model links. It
                        -- deliberately does NOT fall through to
                        -- `i.predicted_price_eur` / `i.estimated_value` the way
                        -- `v_item_values_v1` does: both are member-supplied
                        -- (predicted_price_eur's only writer is add-manual's
                        -- "Estimated value" field, despite the name), so
                        -- including them would let anyone top a category by
                        -- typing a bigger number into their own item.
                        --
                        -- Consequence, stated rather than discovered later: an
                        -- item with no comps contributes 0, and in the 40+
                        -- categories with no sold-comp source that is EVERY
                        -- item. Those categories are ranked by `metric=items`,
                        -- not by value — see docs/P2P_MARKETPLACE_SPEC.md and
                        -- the leaderboard section of MONETIZATION.md.
                        --
                        -- The parity test asserts this is the market-backed
                        -- SUBSET of v_item_values_v1's chain, not a different
                        -- chain: same two expressions, same order, truncated.
                        COALESCE(SUM(
                            COALESCE(
                                -- CATALOGUE-FIRST since 2026-08-19: the live
                                -- model output outranks the snapshot frozen
                                -- into quick_predictions at add/revalue time.
                                -- Same order as v_item_values_v1 and
                                -- /portfolio/items, which is what the parity
                                -- test checks.
                                (SELECT pp.q50 FROM public.price_predictions pp
                                  WHERE pp.item_ref = i.canonical_ref
                               ORDER BY pp.generated_at DESC LIMIT 1),
                                -- The catalogue step was MISSING until
                                -- 2026-08-17 and the board quoted numbers no
                                -- other screen agreed with: 8 of 74 live items
                                -- differed, one member reading EUR 78.90 here
                                -- against EUR 185.15 in their own portfolio.
                                -- Measured by setting request.jwt.claim.sub per
                                -- user and diffing against v_item_values_v1
                                -- item by item.
                                (SELECT qp.q50_eur FROM public.quick_predictions qp
                                  WHERE qp.item_id = i.id
                               ORDER BY qp.created_at DESC LIMIT 1),
                                0
                            )
                        ), 0)::float8 AS total_value
                    FROM public.user_public_profiles p
                    JOIN public.items i
                      ON i.user_id = p.user_id
                     AND i.category = $1
                     AND COALESCE(i.archived, FALSE) = FALSE
                    LEFT JOIN public.user_privacy_settings ps
                      ON ps.user_id = p.user_id
                    WHERE COALESCE(ps.show_item_count, TRUE) IS TRUE
                    {value_gate}
                    GROUP BY p.user_id, p.display_name, p.handle, p.avatar_url
                ),
                ranked AS (
                    -- Ranking happens in an OUTER query on purpose: a window
                    -- function cannot reference a SELECT alias from its own
                    -- level, so `RANK() OVER (ORDER BY total_value)` beside the
                    -- SUM that defines it is a hard error. Caught by running it.
                    SELECT
                        base.*,
                        -- Guarded against 0: a member on this board always has
                        -- at least one item, but a divide-by-zero here would
                        -- take down the whole board rather than one row.
                        CASE WHEN item_count > 0
                             THEN round(100.0 * documented_count / item_count, 1)
                             ELSE 0 END AS documented_pct,
                        COUNT(*) OVER () AS total_ranked
                    FROM base
                ),
                ranked2 AS (
                    -- The rank is computed AFTER documented_pct exists, since
                    -- ordering by it is one of the three metrics. Same reason
                    -- the original rank sits outside `base`: a window function
                    -- cannot reference an alias from its own SELECT level.
                    SELECT
                        ranked.*,
                        RANK() OVER (ORDER BY {order_expr}) AS rank
                    FROM ranked
                )
                SELECT * FROM ranked2
                ORDER BY rank, display_name
                LIMIT $2
                """,
                category_id,
                limit,
            )

        total_ranked = int(rows[0]["total_ranked"]) if rows else 0
        board = [
            CategoryLeaderboardItem(
                rank=int(r["rank"]),
                user_id=str(r["user_id"]),
                display_name=r["display_name"] or "Collector",
                handle=r["handle"],
                avatar_url=r["avatar_url"],
                item_count=int(r["item_count"]),
                value_eur=float(r["total_value"] or 0),
                documented_count=int(r["documented_count"] or 0),
                documented_pct=float(r["documented_pct"] or 0),
                is_you=str(r["user_id"]) == str(current_user_id),
            )
            for r in rows
        ]
        your_rank = next((b.rank for b in board if b.is_you), None)

        logger.info(
            "[social/leaderboard] category=%s metric=%s user=%s returned=%d of %d",
            category_id, metric, current_user_id, len(board), total_ranked,
        )
        # Can this category be ranked by value AT ALL? Measured off the board
        # we just built rather than a hardcoded category list: 40+ categories
        # have no sold-comp source, and since the board sums market-backed
        # value only, every row there is 0.00. Ranking a column of zeros and
        # presenting it as a standing is the `learning_empty_answer_rendered_as_zero`
        # shape — the client shows unit count and documented share instead.
        #
        # Derived, so it self-heals: a category that gains a price source
        # starts offering the value board on its own, and one that loses it
        # stops.
        value_ranking_available = any(e.value_eur > 0 for e in board)

        return CategoryLeaderboardResponse(
            category=category_id,
            metric=metric,
            leaderboard=board,
            your_rank=your_rank,
            total_ranked=total_ranked,
            value_ranking_available=value_ranking_available,
        )

    except asyncpg.PostgresError as e:
        logger.error("[social/leaderboard] DB error: %s", e)
        raise error_response(500, "Category leaderboard failed", code="DB_ERROR")


# ── A collector's categories, with their standing in each ────────────────────


@router.get("/users/{user_id}/categories", response_model=CollectorCategoriesResponse)
async def get_collector_categories(
    user_id: str,
    limit: int = Query(12, ge=1, le=55),
    current_user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_social_search_limit),
):
    """What this collector collects, and where they place in each category.

    This is the profile answer to "what are they into?", which the profile could
    not previously give: it showed totals and achievements, so two members with
    wildly different collections read identically.

    PRIVACY — the same three switches the leaderboard obeys, and they are NOT
    interchangeable:

      * not in `user_public_profiles`  -> nothing at all. Discovery is off, so
        this member is not browsable and the endpoint returns an empty list
        rather than 404, which would confirm the account exists.
      * `show_item_count` false        -> categories are still listed (that you
        collect Pokémon is not the count), but `item_count` is reported as 0 and
        no rank is computed, because a rank derived from a hidden count leaks it
        back by inference.
      * `show_collection_value` false  -> `value_eur` is 0 and `value_visible`
        is False, so the client renders "hidden" rather than "€0".

    Looking at your OWN profile bypasses all three: hiding your collection from
    yourself is not a privacy feature.
    """
    pool = get_db_pool()
    if pool is None:
        return CollectorCategoriesResponse(user_id=user_id, categories=[])

    is_self = str(user_id) == str(current_user_id)

    try:
        async with pool.acquire() as conn:
            if not is_self:
                visible = await conn.fetchval(
                    "SELECT 1 FROM public.user_public_profiles WHERE user_id = $1::uuid",
                    user_id,
                )
                if not visible:
                    return CollectorCategoriesResponse(user_id=user_id, categories=[])

            privacy = await conn.fetchrow(
                """SELECT COALESCE(show_item_count, TRUE)       AS show_items,
                          COALESCE(show_collection_value, TRUE) AS show_value
                     FROM public.user_privacy_settings
                    WHERE user_id = $1::uuid""",
                user_id,
            )
            show_items = True if privacy is None else bool(privacy["show_items"])
            show_value = True if privacy is None else bool(privacy["show_value"])
            if is_self:
                show_items = show_value = True

            # Their categories and totals, then their rank inside each one.
            #
            # Ranking is computed in the SAME statement as the totals rather
            # than by calling the leaderboard endpoint per category: 12 HTTP
            # round trips to our own API to answer one screen is how a profile
            # becomes the slowest page in the app.
            #
            # The value expression is the canonical chain — see the long note on
            # get_category_leaderboard. It is duplicated here for the same
            # reason (v_item_values_v1 is scoped to auth.uid()), and
            # server/tests/test_leaderboard_value_parity.py checks BOTH copies.
            rows = await conn.fetch(
                """
                WITH mine AS (
                    SELECT i.category,
                           COUNT(*) AS item_count,
                           COALESCE(SUM(
                               COALESCE(
                                   (SELECT qp.q50_eur FROM public.quick_predictions qp
                                     WHERE qp.item_id = i.id
                                  ORDER BY qp.created_at DESC LIMIT 1),
                                   (SELECT pp.q50 FROM public.price_predictions pp
                                     WHERE pp.item_ref = i.canonical_ref
                                  ORDER BY pp.generated_at DESC LIMIT 1),
                                   i.predicted_price_eur,
                                   i.estimated_value,
                                   0
                               )
                           ), 0)::float8 AS total_value
                      FROM public.items i
                     WHERE i.user_id = $1::uuid
                       AND COALESCE(i.archived, FALSE) = FALSE
                       AND i.category IS NOT NULL
                  GROUP BY i.category
                ),
                board AS (
                    -- Every ranked collector in the categories this member
                    -- holds. Restricted to `mine` so this is not a full scan of
                    -- every category in the app.
                    SELECT i.category,
                           p.user_id,
                           COUNT(*) AS item_count
                      FROM public.user_public_profiles p
                      JOIN public.items i
                        ON i.user_id = p.user_id
                       AND COALESCE(i.archived, FALSE) = FALSE
                       AND i.category IN (SELECT category FROM mine)
                      LEFT JOIN public.user_privacy_settings ps
                        ON ps.user_id = p.user_id
                     WHERE COALESCE(ps.show_item_count, TRUE) IS TRUE
                  GROUP BY i.category, p.user_id
                ),
                ranked AS (
                    SELECT category,
                           user_id,
                           RANK() OVER (PARTITION BY category ORDER BY item_count DESC) AS rank,
                           COUNT(*) OVER (PARTITION BY category) AS total_ranked
                      FROM board
                )
                SELECT mine.category,
                       mine.item_count,
                       mine.total_value,
                       r.rank,
                       r.total_ranked
                  FROM mine
                  LEFT JOIN ranked r
                    ON r.category = mine.category
                   AND r.user_id = $1::uuid
              ORDER BY mine.item_count DESC, mine.category
                 LIMIT $2
                """,
                user_id,
                limit,
            )

        out = [
            CollectorCategoryStanding(
                category_id=r["category"],
                item_count=int(r["item_count"]) if show_items else 0,
                value_eur=float(r["total_value"] or 0) if show_value else 0.0,
                # A rank is a statement about a count. If the count is hidden,
                # the rank is withheld too — otherwise "#2 of 40" hands back the
                # ordering the switch was meant to withhold.
                rank=int(r["rank"]) if (show_items and r["rank"] is not None) else None,
                total_ranked=(
                    int(r["total_ranked"]) if (show_items and r["total_ranked"] is not None) else None
                ),
            )
            for r in rows
        ]

        logger.info(
            "[social/categories] user=%s viewer=%s returned=%d items_visible=%s value_visible=%s",
            user_id, current_user_id, len(out), show_items, show_value,
        )
        return CollectorCategoriesResponse(
            user_id=user_id, categories=out, value_visible=show_value
        )

    except asyncpg.PostgresError as e:
        logger.error("[social/categories] DB error: %s", e)
        raise error_response(500, "Collector categories failed", code="DB_ERROR")
