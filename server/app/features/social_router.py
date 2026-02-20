"""
Social router — block/unblock users.

Endpoints:
- POST   /social/block/{user_id}   — Block a user
- DELETE /social/block/{user_id}   — Unblock a user
- GET    /social/blocked           — List blocked users
"""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user_id
from app.errors import error_response

router = APIRouter(prefix="/social", tags=["social"])
logger = logging.getLogger(__name__)


def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except (ImportError, RuntimeError, OSError) as e:
        logger.debug(f"DB pool not available: {e}")
        return None


class BlockResponse(BaseModel):
    success: bool
    message: str


class BlockedUserItem(BaseModel):
    user_id: str
    blocked_at: str


class BlockedListResponse(BaseModel):
    blocked: list[BlockedUserItem]


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

    pool = _get_db_pool()
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
                UPDATE chat_threads
                SET status = 'declined'
                WHERE status = 'pending'
                  AND (
                    (sender_id = $1::uuid AND recipient_id = $2::uuid) OR
                    (sender_id = $2::uuid AND recipient_id = $1::uuid)
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

    pool = _get_db_pool()
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
    pool = _get_db_pool()
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
