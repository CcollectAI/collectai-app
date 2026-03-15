"""
Gamification router — achievements, XP, streaks, challenges, leaderboard.

Endpoints:
- GET  /gamification/profile              — User's XP, level, streak, achievement count
- GET  /gamification/profile/{user_id}    — Public gamification profile for any user (no auth)
- GET  /gamification/achievements         — All achievements with user's unlock status
- GET  /gamification/achievements/recent  — Recently unlocked achievements
- GET  /gamification/challenges           — Active challenges with user progress
- POST /gamification/xp                   — Award XP (admin / service role only)
- GET  /gamification/leaderboard          — XP leaderboard (weekly/monthly/alltime)
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id, require_api_key
from app.cache import cache_get, cache_set
from app.db import db_configured, get_conn
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_ip_rate_limit, per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gamification", tags=["Gamification"])

# Rate limits
_leaderboard_limit = per_user_rate_limit(30, window_seconds=60, scope="gamification_leaderboard")
_profile_limit = per_user_rate_limit(60, window_seconds=60, scope="gamification_profile")
_public_profile_limit = per_ip_rate_limit(30, window_seconds=60, scope="gamification_public_profile")

# ---------------------------------------------------------------------------
# XP / levelling helpers
# ---------------------------------------------------------------------------

# XP required per level: level N requires 100 * N XP total (cumulative)
# Level 1 = 0 XP, Level 2 = 100 XP, Level 3 = 300 XP, Level 4 = 600 XP, ...
# Formula: total_xp_for_level = 50 * level * (level - 1)
# Inverse: level = floor((1 + sqrt(1 + 4 * total_xp / 50)) / 2)

def xp_for_level(level: int) -> int:
    """Total cumulative XP required to reach a given level."""
    return 50 * level * (level - 1)


def level_from_xp(total_xp: int) -> int:
    """Calculate level from total XP."""
    if total_xp <= 0:
        return 1
    # Solve 50 * L * (L-1) <= total_xp
    # 50L^2 - 50L - xp = 0  =>  L = (50 + sqrt(2500 + 200*xp)) / 100
    level = int((50 + math.sqrt(2500 + 200 * total_xp)) / 100)
    return max(1, level)


def xp_progress(total_xp: int) -> dict:
    """Return current level, XP within current level, and XP needed for next."""
    level = level_from_xp(total_xp)
    current_floor = xp_for_level(level)
    next_floor = xp_for_level(level + 1)
    return {
        "level": level,
        "current_xp": total_xp - current_floor,
        "xp_to_next": next_floor - current_floor,
        "total_xp": total_xp,
    }


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class GamificationProfile(BaseModel):
    total_xp: int = 0
    level: int = 1
    current_xp: int = 0
    xp_to_next: int = 100
    current_streak: int = 0
    longest_streak: int = 0
    last_activity_date: Optional[str] = None
    weekly_xp: int = 0
    monthly_xp: int = 0
    achievements_unlocked: int = 0
    achievements_total: int = 0


class PublicGamificationProfile(BaseModel):
    """Public-facing gamification profile — no sensitive data."""
    user_id: str
    total_xp: int = 0
    level: int = 1
    current_streak: int = 0
    achievements_unlocked: int = 0
    achievements_total: int = 0
    recent_achievements: list[dict[str, Any]] = Field(default_factory=list)


class AchievementItem(BaseModel):
    id: str
    title: str
    description: str
    icon: str
    category: str
    xp_reward: int
    tier: str
    threshold: Optional[int] = None
    sort_order: int = 0
    unlocked: bool = False
    unlocked_at: Optional[str] = None
    progress: int = 0


class ChallengeItem(BaseModel):
    id: str
    title: str
    description: str
    challenge_type: str
    category: Optional[str] = None
    target_count: int
    xp_reward: int
    start_date: str
    end_date: str
    current_count: int = 0
    completed: bool = False
    completed_at: Optional[str] = None


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_color: Optional[str] = None
    total_xp: int = 0
    level: int = 1
    current_streak: int = 0


class AwardXPRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    amount: int = Field(..., ge=1, le=10000)
    reason: str = Field("manual_award", max_length=200)


# ---------------------------------------------------------------------------
# GET /gamification/profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_profile_limit),
):
    """Get the current user's gamification profile."""
    if not db_configured():
        return {"profile": GamificationProfile().model_dump()}

    try:
        async with get_conn() as conn:
            # Ensure user_gamification row exists
            await conn.execute(
                """
                INSERT INTO public.user_gamification (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
            )

            row = await conn.fetchrow(
                """
                SELECT total_xp, current_streak, longest_streak,
                       last_activity_date, weekly_xp, monthly_xp
                FROM public.user_gamification
                WHERE user_id = $1
                """,
                user_id,
            )

            # Count achievements
            counts = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.user_achievements WHERE user_id = $1) AS unlocked,
                    (SELECT COUNT(*) FROM public.achievements) AS total
                """,
                user_id,
            )

        if row:
            total_xp = row["total_xp"] or 0
            progress = xp_progress(total_xp)
            profile = GamificationProfile(
                total_xp=total_xp,
                level=progress["level"],
                current_xp=progress["current_xp"],
                xp_to_next=progress["xp_to_next"],
                current_streak=row["current_streak"] or 0,
                longest_streak=row["longest_streak"] or 0,
                last_activity_date=row["last_activity_date"].isoformat() if row["last_activity_date"] else None,
                weekly_xp=row["weekly_xp"] or 0,
                monthly_xp=row["monthly_xp"] or 0,
                achievements_unlocked=counts["unlocked"] if counts else 0,
                achievements_total=counts["total"] if counts else 0,
            )
        else:
            profile = GamificationProfile(
                achievements_total=counts["total"] if counts else 0,
            )

        return {"profile": profile.model_dump()}
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error fetching profile: %s", e)
        raise error_response(500, "Failed to fetch gamification profile", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /gamification/profile/{user_id} — Public profile for any user
# ---------------------------------------------------------------------------

@router.get("/profile/{user_id}")
async def get_public_profile(
    user_id: str = Path(..., min_length=1, max_length=100),
    _rl: None = Depends(_public_profile_limit),
) -> dict[str, Any]:
    """Get a public gamification profile for any user (no auth required)."""
    # Validate UUID format
    try:
        UUID(user_id)
    except ValueError:
        raise error_response(400, "Invalid user ID format", code=ErrorCode.VALIDATION_ERROR)

    if not db_configured():
        return {"profile": PublicGamificationProfile(user_id=user_id).model_dump()}

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT total_xp, current_streak
                FROM public.user_gamification
                WHERE user_id = $1
                """,
                user_id,
            )

            counts = await conn.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.user_achievements WHERE user_id = $1) AS unlocked,
                    (SELECT COUNT(*) FROM public.achievements) AS total
                """,
                user_id,
            )

            # Fetch up to 5 most recent unlocked achievements (public info only)
            recent_rows = await conn.fetch(
                """
                SELECT a.id, a.title, a.icon, a.tier, ua.unlocked_at
                FROM public.user_achievements ua
                JOIN public.achievements a ON a.id = ua.achievement_id
                WHERE ua.user_id = $1
                ORDER BY ua.unlocked_at DESC
                LIMIT 5
                """,
                user_id,
            )

        if row:
            total_xp = row["total_xp"] or 0
            level = level_from_xp(total_xp)
            profile = PublicGamificationProfile(
                user_id=user_id,
                total_xp=total_xp,
                level=level,
                current_streak=row["current_streak"] or 0,
                achievements_unlocked=counts["unlocked"] if counts else 0,
                achievements_total=counts["total"] if counts else 0,
                recent_achievements=[
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "icon": r["icon"],
                        "tier": r["tier"],
                        "unlocked_at": r["unlocked_at"].isoformat() if r["unlocked_at"] else None,
                    }
                    for r in recent_rows
                ],
            )
        else:
            profile = PublicGamificationProfile(
                user_id=user_id,
                achievements_total=counts["total"] if counts else 0,
            )

        return {"profile": profile.model_dump()}
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error fetching public profile for %s: %s", user_id, e)
        raise error_response(500, "Failed to fetch gamification profile", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /gamification/achievements
# ---------------------------------------------------------------------------

@router.get("/achievements")
async def list_achievements(
    user_id: str = Depends(get_current_user_id),
    category: Optional[str] = Query(None, max_length=50),
):
    """List all achievements with the current user's unlock status."""
    if not db_configured():
        return {"achievements": []}

    try:
        async with get_conn() as conn:
            if category:
                rows = await conn.fetch(
                    """
                    SELECT a.id, a.title, a.description, a.icon, a.category,
                           a.xp_reward, a.tier, a.threshold, a.sort_order,
                           ua.unlocked_at, ua.progress
                    FROM public.achievements a
                    LEFT JOIN public.user_achievements ua
                        ON ua.achievement_id = a.id AND ua.user_id = $1
                    WHERE a.category = $2
                    ORDER BY a.sort_order
                    """,
                    user_id,
                    category,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT a.id, a.title, a.description, a.icon, a.category,
                           a.xp_reward, a.tier, a.threshold, a.sort_order,
                           ua.unlocked_at, ua.progress
                    FROM public.achievements a
                    LEFT JOIN public.user_achievements ua
                        ON ua.achievement_id = a.id AND ua.user_id = $1
                    ORDER BY a.sort_order
                    """,
                    user_id,
                )

        achievements = [
            AchievementItem(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                icon=r["icon"],
                category=r["category"],
                xp_reward=r["xp_reward"],
                tier=r["tier"],
                threshold=r["threshold"],
                sort_order=r["sort_order"],
                unlocked=r["unlocked_at"] is not None,
                unlocked_at=r["unlocked_at"].isoformat() if r["unlocked_at"] else None,
                progress=r["progress"] or 0,
            ).model_dump()
            for r in rows
        ]

        return {"achievements": achievements}
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error listing achievements: %s", e)
        raise error_response(500, "Failed to list achievements", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /gamification/achievements/recent
# ---------------------------------------------------------------------------

@router.get("/achievements/recent")
async def recent_achievements(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get recently unlocked achievements for the current user."""
    if not db_configured():
        return {"achievements": []}

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT a.id, a.title, a.description, a.icon, a.category,
                       a.xp_reward, a.tier, a.threshold, a.sort_order,
                       ua.unlocked_at, ua.progress
                FROM public.user_achievements ua
                JOIN public.achievements a ON a.id = ua.achievement_id
                WHERE ua.user_id = $1
                ORDER BY ua.unlocked_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )

        achievements = [
            AchievementItem(
                id=r["id"],
                title=r["title"],
                description=r["description"],
                icon=r["icon"],
                category=r["category"],
                xp_reward=r["xp_reward"],
                tier=r["tier"],
                threshold=r["threshold"],
                sort_order=r["sort_order"],
                unlocked=True,
                unlocked_at=r["unlocked_at"].isoformat() if r["unlocked_at"] else None,
                progress=r["progress"] or 0,
            ).model_dump()
            for r in rows
        ]

        return {"achievements": achievements}
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error fetching recent achievements: %s", e)
        raise error_response(500, "Failed to fetch recent achievements", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /gamification/challenges
# ---------------------------------------------------------------------------

@router.get("/challenges")
async def list_challenges(
    user_id: str = Depends(get_current_user_id),
    challenge_type: Optional[str] = Query(None, pattern="^(weekly|monthly|special)$"),
):
    """List active challenges with the current user's progress."""
    if not db_configured():
        return {"challenges": []}

    try:
        today = date.today()
        async with get_conn() as conn:
            if challenge_type:
                rows = await conn.fetch(
                    """
                    SELECT c.id, c.title, c.description, c.challenge_type,
                           c.category, c.target_count, c.xp_reward,
                           c.start_date, c.end_date,
                           ucp.current_count, ucp.completed, ucp.completed_at
                    FROM public.challenges c
                    LEFT JOIN public.user_challenge_progress ucp
                        ON ucp.challenge_id = c.id AND ucp.user_id = $1
                    WHERE c.active = true
                      AND c.start_date <= $2
                      AND c.end_date >= $2
                      AND c.challenge_type = $3
                    ORDER BY c.end_date ASC
                    """,
                    user_id,
                    today,
                    challenge_type,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT c.id, c.title, c.description, c.challenge_type,
                           c.category, c.target_count, c.xp_reward,
                           c.start_date, c.end_date,
                           ucp.current_count, ucp.completed, ucp.completed_at
                    FROM public.challenges c
                    LEFT JOIN public.user_challenge_progress ucp
                        ON ucp.challenge_id = c.id AND ucp.user_id = $1
                    WHERE c.active = true
                      AND c.start_date <= $2
                      AND c.end_date >= $2
                    ORDER BY c.end_date ASC
                    """,
                    user_id,
                    today,
                )

        challenges = [
            ChallengeItem(
                id=str(r["id"]),
                title=r["title"],
                description=r["description"],
                challenge_type=r["challenge_type"],
                category=r["category"],
                target_count=r["target_count"],
                xp_reward=r["xp_reward"],
                start_date=r["start_date"].isoformat(),
                end_date=r["end_date"].isoformat(),
                current_count=r["current_count"] or 0,
                completed=r["completed"] or False,
                completed_at=r["completed_at"].isoformat() if r["completed_at"] else None,
            ).model_dump()
            for r in rows
        ]

        return {"challenges": challenges}
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error listing challenges: %s", e)
        raise error_response(500, "Failed to list challenges", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# POST /gamification/xp — Award XP (admin / service role)
# ---------------------------------------------------------------------------

@router.post("/xp")
async def award_xp(
    req: AwardXPRequest,
    _auth: bool = Depends(require_api_key),
):
    """
    Award XP to a user. Requires X-API-Key header (service role).

    Also updates:
    - level (recalculated from new total_xp)
    - weekly_xp / monthly_xp accumulators
    - streak (bumps if last_activity_date was yesterday or today)
    - streak achievements auto-check
    """
    if not db_configured():
        return {"awarded": True, "amount": req.amount, "new_total": req.amount}

    try:
        async with get_conn() as conn:
            today = date.today()

            # Upsert gamification row and award XP atomically
            row = await conn.fetchrow(
                """
                INSERT INTO public.user_gamification (user_id, total_xp, weekly_xp, monthly_xp, last_activity_date, updated_at)
                VALUES ($1, $2, $2, $2, $3, now())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    total_xp = public.user_gamification.total_xp + $2,
                    weekly_xp = public.user_gamification.weekly_xp + $2,
                    monthly_xp = public.user_gamification.monthly_xp + $2,
                    current_streak = CASE
                        WHEN public.user_gamification.last_activity_date = $3 THEN public.user_gamification.current_streak
                        WHEN public.user_gamification.last_activity_date = $3 - INTERVAL '1 day' THEN public.user_gamification.current_streak + 1
                        ELSE 1
                    END,
                    longest_streak = GREATEST(
                        public.user_gamification.longest_streak,
                        CASE
                            WHEN public.user_gamification.last_activity_date = $3 THEN public.user_gamification.current_streak
                            WHEN public.user_gamification.last_activity_date = $3 - INTERVAL '1 day' THEN public.user_gamification.current_streak + 1
                            ELSE 1
                        END
                    ),
                    last_activity_date = $3,
                    updated_at = now()
                RETURNING total_xp, current_streak, longest_streak
                """,
                req.user_id,
                req.amount,
                today,
            )

            new_total = row["total_xp"]
            new_level = level_from_xp(new_total)
            current_streak = row["current_streak"]

            # Update level
            await conn.execute(
                "UPDATE public.user_gamification SET level = $2 WHERE user_id = $1",
                req.user_id,
                new_level,
            )

            # Auto-check streak achievements
            streak_achievements = [
                ("streak_3", 3),
                ("streak_7", 7),
                ("streak_14", 14),
                ("streak_30", 30),
            ]
            for ach_id, threshold in streak_achievements:
                if current_streak >= threshold:
                    await conn.execute(
                        """
                        INSERT INTO public.user_achievements (user_id, achievement_id, progress)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, achievement_id) DO UPDATE SET progress = $3
                        """,
                        req.user_id,
                        ach_id,
                        current_streak,
                    )

        logger.info(
            "[gamification] XP awarded: user=%s amount=%d reason=%s new_total=%d level=%d",
            req.user_id,
            req.amount,
            req.reason,
            new_total,
            new_level,
        )

        progress = xp_progress(new_total)
        return {
            "awarded": True,
            "amount": req.amount,
            "reason": req.reason,
            "new_total": new_total,
            "level": new_level,
            "current_xp": progress["current_xp"],
            "xp_to_next": progress["xp_to_next"],
            "current_streak": current_streak,
        }
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error awarding XP: %s", e)
        raise error_response(500, "Failed to award XP", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /gamification/leaderboard
# ---------------------------------------------------------------------------

@router.get("/leaderboard")
async def get_leaderboard(
    period: str = Query("weekly", pattern="^(weekly|monthly|alltime)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_leaderboard_limit),
):
    """
    Get the XP leaderboard.

    Periods:
    - weekly: ranked by weekly_xp
    - monthly: ranked by monthly_xp
    - alltime: ranked by total_xp
    """
    if not db_configured():
        return {"leaderboard": [], "user_rank": None, "total_count": 0}

    # SAFETY: xp_column is always one of 3 hardcoded literals from the dict
    # lookup above. The dict key is validated by FastAPI's regex pattern
    # (^(weekly|monthly|alltime)$), the dict maps to a fixed set, and the
    # assert below provides runtime defense-in-depth. This is NOT user input.
    _XP_COLUMNS = {
        "weekly": "weekly_xp",
        "monthly": "monthly_xp",
        "alltime": "total_xp",
    }
    xp_column = _XP_COLUMNS[period]

    assert xp_column in _XP_COLUMNS.values(), f"Invalid xp_column: {xp_column}"

    # Cache leaderboard page (60s TTL) — keyed by period+limit+offset
    _LEADERBOARD_CACHE_TTL = 60
    cache_key = f"leaderboard:{period}:{limit}:{offset}"
    cached_page = cache_get(cache_key)

    try:
        if cached_page is not None:
            leaderboard = cached_page["leaderboard"]
            total_count = cached_page["total_count"]
        else:
            async with get_conn() as conn:
                # Fetch leaderboard page with user profile info
                rows = await conn.fetch(
                    f"""
                    SELECT
                        ug.user_id,
                        ug.{xp_column} AS xp,
                        ug.total_xp,
                        ug.level,
                        ug.current_streak,
                        p.display_name,
                        p.avatar_url,
                        p.avatar_color
                    FROM public.user_gamification ug
                    LEFT JOIN public.profiles p ON p.id = ug.user_id
                    WHERE ug.{xp_column} > 0
                    ORDER BY ug.{xp_column} DESC, ug.user_id
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )

                # Total count for pagination
                total_row = await conn.fetchrow(
                    f"SELECT COUNT(*) AS cnt FROM public.user_gamification WHERE {xp_column} > 0"
                )
                total_count = total_row["cnt"] if total_row else 0

            leaderboard = [
                LeaderboardEntry(
                    rank=offset + i + 1,
                    user_id=str(r["user_id"]),
                    display_name=r["display_name"],
                    avatar_url=r["avatar_url"],
                    avatar_color=r.get("avatar_color"),
                    total_xp=r["total_xp"] or 0,
                    level=r["level"] or 1,
                    current_streak=r["current_streak"] or 0,
                ).model_dump()
                for i, r in enumerate(rows)
            ]

            cache_set(cache_key, {"leaderboard": leaderboard, "total_count": total_count}, ttl=_LEADERBOARD_CACHE_TTL)

        # User rank is always fetched fresh (per-user, cheap query)
        async with get_conn() as conn:
            rank_row = await conn.fetchrow(
                f"""
                SELECT COUNT(*) + 1 AS rank
                FROM public.user_gamification
                WHERE {xp_column} > COALESCE(
                    (SELECT {xp_column} FROM public.user_gamification WHERE user_id = $1), 0
                )
                """,
                user_id,
            )
            user_rank = rank_row["rank"] if rank_row else None

        return {
            "leaderboard": leaderboard,
            "period": period,
            "user_rank": user_rank,
            "total_count": total_count,
        }
    except asyncpg.PostgresError as e:
        logger.error("[gamification] Error fetching leaderboard: %s", e)
        raise error_response(500, "Failed to fetch leaderboard", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# Internal helper: record activity + check achievements
# ---------------------------------------------------------------------------

async def record_activity_xp(
    conn: asyncpg.Connection,
    user_id: str,
    xp_amount: int,
    achievement_checks: Optional[list[tuple[str, int]]] = None,
) -> dict:
    """
    Internal helper for other routers to award XP and check achievements.

    Args:
        conn: Active DB connection
        user_id: User to award
        xp_amount: XP to add
        achievement_checks: Optional list of (achievement_id, current_progress)
                           tuples to upsert

    Returns:
        Dict with new_total, level, streak info
    """
    today = date.today()

    row = await conn.fetchrow(
        """
        INSERT INTO public.user_gamification (user_id, total_xp, weekly_xp, monthly_xp, last_activity_date, updated_at)
        VALUES ($1, $2, $2, $2, $3, now())
        ON CONFLICT (user_id)
        DO UPDATE SET
            total_xp = public.user_gamification.total_xp + $2,
            weekly_xp = public.user_gamification.weekly_xp + $2,
            monthly_xp = public.user_gamification.monthly_xp + $2,
            current_streak = CASE
                WHEN public.user_gamification.last_activity_date = $3 THEN public.user_gamification.current_streak
                WHEN public.user_gamification.last_activity_date = $3 - INTERVAL '1 day' THEN public.user_gamification.current_streak + 1
                ELSE 1
            END,
            longest_streak = GREATEST(
                public.user_gamification.longest_streak,
                CASE
                    WHEN public.user_gamification.last_activity_date = $3 THEN public.user_gamification.current_streak
                    WHEN public.user_gamification.last_activity_date = $3 - INTERVAL '1 day' THEN public.user_gamification.current_streak + 1
                    ELSE 1
                END
            ),
            last_activity_date = $3,
            updated_at = now()
        RETURNING total_xp, current_streak, longest_streak, level
        """,
        user_id,
        xp_amount,
        today,
    )

    new_total = row["total_xp"]
    new_level = level_from_xp(new_total)
    current_streak = row["current_streak"]

    # Update level if changed
    if new_level != row["level"]:
        await conn.execute(
            "UPDATE public.user_gamification SET level = $2 WHERE user_id = $1",
            user_id,
            new_level,
        )

    # Check streak achievements
    streak_milestones = [(3, "streak_3"), (7, "streak_7"), (14, "streak_14"), (30, "streak_30")]
    for threshold, ach_id in streak_milestones:
        if current_streak >= threshold:
            await conn.execute(
                """
                INSERT INTO public.user_achievements (user_id, achievement_id, progress)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, achievement_id) DO UPDATE SET progress = $3
                """,
                user_id,
                ach_id,
                current_streak,
            )

    # Additional achievement checks
    if achievement_checks:
        for ach_id, progress in achievement_checks:
            # Look up threshold
            ach_row = await conn.fetchrow(
                "SELECT threshold, xp_reward FROM public.achievements WHERE id = $1",
                ach_id,
            )
            if ach_row and ach_row["threshold"] and progress >= ach_row["threshold"]:
                await conn.execute(
                    """
                    INSERT INTO public.user_achievements (user_id, achievement_id, progress)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, achievement_id) DO UPDATE SET progress = $3
                    """,
                    user_id,
                    ach_id,
                    progress,
                )

    return {
        "total_xp": new_total,
        "level": new_level,
        "current_streak": current_streak,
    }
