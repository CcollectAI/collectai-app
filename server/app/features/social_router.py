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
            rows = await conn.fetch(
                """
                SELECT
                    user_id,
                    display_name,
                    handle,
                    avatar_url,
                    avatar_color
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
