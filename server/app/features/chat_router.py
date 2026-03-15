"""
Chat router — DM thread management and messaging.

Endpoints:
- GET    /chat/threads                       — List user's DM threads
- GET    /chat/threads/{thread_id}/messages   — Get messages for a thread (paginated)
- POST   /chat/threads/{thread_id}/messages   — Send a message
- PATCH  /chat/threads/{thread_id}/read       — Mark thread as read
- DELETE /chat/messages/{message_id}          — Delete own message (soft delete)
- PATCH  /chat/messages/{message_id}          — Edit own message (within 15min)
- GET    /chat/unread-count                   — Get total unread count
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# Rate limits
_send_message_limit = per_user_rate_limit(30, window_seconds=60, scope="chat_send")
_read_limit = per_user_rate_limit(60, window_seconds=60, scope="chat_read")

# Edit window: 15 minutes
EDIT_WINDOW_SECONDS = 15 * 60


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class EditMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_uuid(value: str, field_name: str = "id") -> UUID:
    """Validate and return a UUID, raising a 400 on invalid format."""
    try:
        return UUID(value)
    except ValueError:
        raise error_response(400, f"Invalid {field_name} format", code=ErrorCode.VALIDATION_ERROR)


async def _notify_new_message(
    conn: asyncpg.Connection,
    sender_id: str,
    recipient_id: str,
    thread_id: str,
    text_preview: str,
) -> None:
    """Send a push notification for a new chat message."""
    try:
        from app.push import send_push_to_user

        # Get sender display name for the notification title
        sender_row = await conn.fetchrow(
            "SELECT display_name FROM user_public_profiles WHERE user_id = $1::uuid",
            sender_id,
        )
        sender_name = sender_row["display_name"] if sender_row else "Someone"

        # Truncate preview
        preview = text_preview[:100] + "..." if len(text_preview) > 100 else text_preview

        await send_push_to_user(
            conn,
            recipient_id,
            title=f"Message from {sender_name}",
            body=preview,
            data={"type": "chat_message", "thread_id": thread_id},
        )
    except ImportError:
        logger.debug("[chat] Push notification module not available — skipping notification")
    except Exception as exc:
        # Never let notification failure break message sending
        logger.warning("[chat] Failed to send push notification: %s", exc)


async def _check_not_blocked(
    conn: asyncpg.Connection,
    user_id: str,
    other_user_id: str,
) -> None:
    """Raise 403 if either user has blocked the other."""
    blocked = await conn.fetchval(
        """
        SELECT 1 FROM user_blocks
        WHERE (blocker_id = $1::uuid AND blocked_id = $2::uuid)
           OR (blocker_id = $2::uuid AND blocked_id = $1::uuid)
        LIMIT 1
        """,
        user_id,
        other_user_id,
    )
    if blocked:
        raise error_response(403, "Cannot message this user", code=ErrorCode.FORBIDDEN)


async def _get_thread_participant(
    conn: asyncpg.Connection,
    thread_id: str,
    user_id: str,
) -> Optional[str]:
    """Return the other participant's user_id if user_id is a member, else None."""
    row = await conn.fetchrow(
        """
        SELECT requester_id, responder_id
        FROM dm_threads
        WHERE id = $1::uuid
          AND (requester_id = $2::uuid OR responder_id = $2::uuid)
        """,
        thread_id,
        user_id,
    )
    if not row:
        return None
    if str(row["requester_id"]) == user_id:
        return str(row["responder_id"])
    return str(row["requester_id"])


# ---------------------------------------------------------------------------
# GET /chat/threads
# ---------------------------------------------------------------------------


@router.get("/threads", summary="List DM threads")
async def list_threads(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_read_limit),
) -> Dict[str, Any]:
    """Return the current user's DM threads from the inbox view."""
    pool = get_db_pool()
    if pool is None:
        return {"threads": [], "total_count": 0}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT thread_id, user_id, other_user_id, other_display_name, other_avatar_url, last_message_at, last_message_body, unread_count, created_at, updated_at
                FROM v_chat_inbox_v1
                WHERE user_id = $1::uuid
                ORDER BY last_message_at DESC NULLS LAST
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM v_chat_inbox_v1 WHERE user_id = $1::uuid",
                user_id,
            )

        threads = [dict(r) for r in rows]
        # Serialize datetimes
        for t in threads:
            for key in ("last_message_at", "created_at", "updated_at"):
                if key in t and isinstance(t[key], datetime):
                    t[key] = t[key].isoformat()
            # Serialize UUIDs
            for key in ("thread_id", "user_id", "other_user_id"):
                if key in t and t[key] is not None:
                    t[key] = str(t[key])

        logger.info("[chat/threads] user=%s count=%d", user_id, len(threads))
        return {"threads": threads, "total_count": total or 0}

    except asyncpg.PostgresError as e:
        logger.error("[chat/threads] DB error: %s", e)
        raise error_response(500, "Failed to fetch threads", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /chat/threads/{thread_id}/messages
# ---------------------------------------------------------------------------


@router.get("/threads/{thread_id}/messages", summary="Get thread messages")
async def get_thread_messages(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_read_limit),
) -> Dict[str, Any]:
    """Return paginated messages for a thread. IDOR-safe: user must be a participant."""
    _validate_uuid(thread_id, "thread_id")

    pool = get_db_pool()
    if pool is None:
        return {"messages": [], "total_count": 0}

    try:
        async with pool.acquire() as conn:
            # Ownership check — user must be a participant
            other = await _get_thread_participant(conn, thread_id, user_id)
            if other is None:
                raise error_response(404, "Thread not found", code=ErrorCode.NOT_FOUND)

            rows = await conn.fetch(
                """
                SELECT id, thread_id, sender_id, body, created_at, edited_at, deleted_at
                FROM chat_messages_v1
                WHERE thread_id = $1::uuid
                  AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                thread_id,
                limit,
                offset,
            )
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM chat_messages_v1
                WHERE thread_id = $1::uuid AND deleted_at IS NULL
                """,
                thread_id,
            )

        messages = []
        for r in rows:
            messages.append({
                "id": str(r["id"]),
                "thread_id": str(r["thread_id"]),
                "sender_id": str(r["sender_id"]),
                "body": r["body"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "edited_at": r["edited_at"].isoformat() if r["edited_at"] else None,
            })

        logger.info("[chat/messages] thread=%s user=%s count=%d", thread_id, user_id, len(messages))
        return {"messages": messages, "total_count": total or 0}

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[chat/messages] DB error: %s", e)
        raise error_response(500, "Failed to fetch messages", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# POST /chat/threads/{thread_id}/messages
# ---------------------------------------------------------------------------


@router.post("/threads/{thread_id}/messages", summary="Send a message")
async def send_message(
    thread_id: str,
    req: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_send_message_limit),
) -> Dict[str, Any]:
    """Send a message in a DM thread. Triggers push notification to the other user."""
    _validate_uuid(thread_id, "thread_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            # Ownership check
            other_user_id = await _get_thread_participant(conn, thread_id, user_id)
            if other_user_id is None:
                raise error_response(404, "Thread not found", code=ErrorCode.NOT_FOUND)

            # Block check
            await _check_not_blocked(conn, user_id, other_user_id)

            # Send via RPC (handles dm_messages insert + thread updated_at)
            row = await conn.fetchrow(
                "SELECT * FROM rpc_send_message_v1($1::uuid, $2::uuid, $3::text)",
                thread_id,
                user_id,
                req.content,
            )

            if row is None:
                raise error_response(500, "Failed to send message", code=ErrorCode.DB_ERROR)

            message = dict(row)
            # Serialize
            for key in ("id", "thread_id", "sender_id"):
                if key in message and message[key] is not None:
                    message[key] = str(message[key])
            for key in ("created_at", "edited_at"):
                if key in message and isinstance(message[key], datetime):
                    message[key] = message[key].isoformat()

            # Push notification (best effort, non-blocking)
            await _notify_new_message(conn, user_id, other_user_id, thread_id, req.content)

        logger.info("[chat/send] thread=%s sender=%s", thread_id, user_id)
        return {"message": message}

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[chat/send] DB error: %s", e)
        raise error_response(500, "Failed to send message", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# PATCH /chat/threads/{thread_id}/read
# ---------------------------------------------------------------------------


@router.patch("/threads/{thread_id}/read", summary="Mark thread as read")
async def mark_thread_read(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_read_limit),
) -> Dict[str, Any]:
    """Mark all messages in a thread as read for the current user."""
    _validate_uuid(thread_id, "thread_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            # Ownership check
            other = await _get_thread_participant(conn, thread_id, user_id)
            if other is None:
                raise error_response(404, "Thread not found", code=ErrorCode.NOT_FOUND)

            # Update last_read_at for this user on the thread
            await conn.execute(
                """
                UPDATE dm_threads
                SET last_read_at = now()
                WHERE id = $1::uuid
                  AND (requester_id = $2::uuid OR responder_id = $2::uuid)
                """,
                thread_id,
                user_id,
            )

        logger.info("[chat/read] thread=%s user=%s", thread_id, user_id)
        return {"ok": True}

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[chat/read] DB error: %s", e)
        raise error_response(500, "Failed to mark thread as read", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# DELETE /chat/messages/{message_id}
# ---------------------------------------------------------------------------


@router.delete("/messages/{message_id}", summary="Delete own message")
async def delete_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_send_message_limit),
) -> Dict[str, Any]:
    """Soft-delete a message. Only the sender can delete their own messages (IDOR check)."""
    _validate_uuid(message_id, "message_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            # IDOR check: verify ownership
            row = await conn.fetchrow(
                """
                SELECT sender_id, deleted_at
                FROM dm_messages
                WHERE id = $1::uuid
                """,
                message_id,
            )
            if row is None:
                raise error_response(404, "Message not found", code=ErrorCode.NOT_FOUND)
            if str(row["sender_id"]) != user_id:
                raise error_response(403, "Cannot delete another user's message", code=ErrorCode.FORBIDDEN)
            if row["deleted_at"] is not None:
                return {"ok": True, "already_deleted": True}

            # Soft delete
            await conn.execute(
                """
                UPDATE dm_messages
                SET deleted_at = now()
                WHERE id = $1::uuid AND sender_id = $2::uuid
                """,
                message_id,
                user_id,
            )

        logger.info("[chat/delete] message=%s user=%s", message_id, user_id)
        return {"ok": True}

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[chat/delete] DB error: %s", e)
        raise error_response(500, "Failed to delete message", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# PATCH /chat/messages/{message_id}
# ---------------------------------------------------------------------------


@router.patch("/messages/{message_id}", summary="Edit own message")
async def edit_message(
    message_id: str,
    req: EditMessageRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_send_message_limit),
) -> Dict[str, Any]:
    """Edit a message within a 15-minute window. Only the sender can edit (IDOR check)."""
    _validate_uuid(message_id, "message_id")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            # IDOR check + fetch creation time
            row = await conn.fetchrow(
                """
                SELECT sender_id, created_at, deleted_at
                FROM dm_messages
                WHERE id = $1::uuid
                """,
                message_id,
            )
            if row is None:
                raise error_response(404, "Message not found", code=ErrorCode.NOT_FOUND)
            if str(row["sender_id"]) != user_id:
                raise error_response(403, "Cannot edit another user's message", code=ErrorCode.FORBIDDEN)
            if row["deleted_at"] is not None:
                raise error_response(400, "Cannot edit a deleted message", code=ErrorCode.VALIDATION_ERROR)

            # Check 15-minute edit window
            created_at = row["created_at"]
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
            if elapsed > EDIT_WINDOW_SECONDS:
                raise error_response(
                    400,
                    "Edit window expired (15 minutes)",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            # Perform edit
            updated = await conn.fetchrow(
                """
                UPDATE dm_messages
                SET body = $3, edited_at = now()
                WHERE id = $1::uuid AND sender_id = $2::uuid
                RETURNING id, thread_id, sender_id, body, created_at, edited_at
                """,
                message_id,
                user_id,
                req.content,
            )

        if updated is None:
            raise error_response(500, "Failed to edit message", code=ErrorCode.DB_ERROR)

        message = {
            "id": str(updated["id"]),
            "thread_id": str(updated["thread_id"]),
            "sender_id": str(updated["sender_id"]),
            "body": updated["body"],
            "created_at": updated["created_at"].isoformat() if updated["created_at"] else None,
            "edited_at": updated["edited_at"].isoformat() if updated["edited_at"] else None,
        }

        logger.info("[chat/edit] message=%s user=%s", message_id, user_id)
        return {"message": message}

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[chat/edit] DB error: %s", e)
        raise error_response(500, "Failed to edit message", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /chat/unread-count
# ---------------------------------------------------------------------------


@router.get("/unread-count", summary="Get total unread count")
async def get_unread_count(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_read_limit),
) -> Dict[str, Any]:
    """Return the total number of unread DM threads for the current user."""
    pool = get_db_pool()
    if pool is None:
        return {"unread_count": 0}

    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM v_chat_inbox_v1
                WHERE user_id = $1::uuid AND unread_count > 0
                """,
                user_id,
            )

        return {"unread_count": count or 0}

    except asyncpg.PostgresError as e:
        logger.error("[chat/unread-count] DB error: %s", e)
        raise error_response(500, "Failed to fetch unread count", code=ErrorCode.DB_ERROR)
