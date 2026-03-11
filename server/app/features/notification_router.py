"""
Push notification management router.

Endpoints:
- POST /notifications/register       — Register an Expo push token
- DELETE /notifications/register      — Unregister a push token
- GET  /notifications/tokens          — List active tokens for current user
- GET  /notifications/preferences     — Get notification preferences
- PUT  /notifications/preferences     — Update notification preferences
- GET  /notifications/history         — Paginated notification history
- PATCH /notifications/{id}/read      — Mark single notification as read
- POST /notifications/mark-all-read   — Mark all notifications as read
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import db_configured, get_conn
from app.errors import error_response
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Per-user: 10 token registrations per hour (prevent push token spam)
_register_token_limit = per_user_rate_limit(10, window_seconds=3600, scope="push_token_register")

# Per-user: 60 history reads per minute (generous but bounded)
_history_read_limit = per_user_rate_limit(60, window_seconds=60, scope="notification_history_read")

# Per-user: 30 mark-read operations per minute
_mark_read_limit = per_user_rate_limit(30, window_seconds=60, scope="notification_mark_read")

# ---------------------------------------------------------------------------
# Table bootstrap — idempotent, called once on first endpoint hit
# ---------------------------------------------------------------------------
_table_ensured = False


async def _ensure_table() -> None:
    """Create notification_history table if it does not exist (idempotent)."""
    global _table_ensured
    if _table_ensured or not db_configured():
        return
    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    data JSONB DEFAULT '{}',
                    deep_link TEXT,
                    read_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS idx_notification_history_user_created
                    ON notification_history(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_notification_history_user_unread
                    ON notification_history(user_id) WHERE read_at IS NULL;
                """
            )
        _table_ensured = True
        logger.info("[notifications] notification_history table ensured")
    except Exception as exc:
        logger.warning("[notifications] Failed to ensure notification_history table: %s", exc)

# Default notification preferences
DEFAULT_NOTIFICATION_PREFERENCES = {
    "value_changes": True,
    "item_value_changes": True,
    "weekly_digest": True,
    "price_alerts": True,
    "deal_alerts": True,
    "chat_messages": True,
    "connection_requests": True,
    "event_announcements": True,
}


class RegisterTokenRequest(BaseModel):
    push_token: str = Field(..., min_length=10, max_length=200)
    platform: str = Field("unknown", max_length=20)
    device_name: Optional[str] = Field(None, max_length=100)


class UnregisterTokenRequest(BaseModel):
    push_token: str = Field(..., min_length=10, max_length=200)


@router.post("/register", summary="Register push token")
async def register_push_token(
    req: RegisterTokenRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_register_token_limit),
):
    """Register an Expo push token for the current user."""
    if not req.push_token.startswith("ExponentPushToken["):
        raise error_response(400, "Invalid Expo push token format", code="VALIDATION_ERROR")

    if not db_configured():
        logger.info("[notifications] Token registered (no DB): user=%s", user_id)
        return {"registered": True, "push_token": req.push_token}

    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO public.user_push_tokens (user_id, push_token, platform, device_name)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, push_token)
                DO UPDATE SET active = true, platform = $3, device_name = $4, updated_at = now()
                """,
                user_id,
                req.push_token,
                req.platform,
                req.device_name,
            )
        logger.info("[notifications] Token registered: user=%s, platform=%s", user_id, req.platform)
        return {"registered": True, "push_token": req.push_token}
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error registering token: %s", e)
        raise error_response(500, "Failed to register push token", code="DB_ERROR")


@router.delete("/register", summary="Unregister push token")
async def unregister_push_token(
    req: UnregisterTokenRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Deactivate a push token (soft delete)."""
    if not db_configured():
        return {"unregistered": True}

    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                UPDATE public.user_push_tokens
                SET active = false, updated_at = now()
                WHERE user_id = $1 AND push_token = $2
                """,
                user_id,
                req.push_token,
            )
        logger.info("[notifications] Token unregistered: user=%s", user_id)
        return {"unregistered": True}
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error unregistering token: %s", e)
        raise error_response(500, "Failed to unregister push token", code="DB_ERROR")


@router.get("/tokens", summary="List active push tokens")
async def list_push_tokens(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all active push tokens for the current user."""
    if not db_configured():
        return {"tokens": []}

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT push_token, platform, device_name, created_at
                FROM public.user_push_tokens
                WHERE user_id = $1 AND active = true
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
        return {
            "tokens": [
                {
                    "push_token": r["push_token"],
                    "platform": r["platform"],
                    "device_name": r["device_name"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        }
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error listing tokens: %s", e)
        raise error_response(500, "Failed to list push tokens", code="DB_ERROR")


# ---------------------------------------------------------------------------
# Notification Preferences
# ---------------------------------------------------------------------------


class NotificationPreferencesUpdate(BaseModel):
    value_changes: Optional[bool] = None
    item_value_changes: Optional[bool] = None
    weekly_digest: Optional[bool] = None
    price_alerts: Optional[bool] = None
    deal_alerts: Optional[bool] = None
    chat_messages: Optional[bool] = None
    connection_requests: Optional[bool] = None
    event_announcements: Optional[bool] = None


@router.get("/preferences", summary="Get notification preferences")
async def get_notification_preferences(
    user_id: str = Depends(get_current_user_id),
):
    """Get the current user's notification preferences."""
    if not db_configured():
        return {"preferences": DEFAULT_NOTIFICATION_PREFERENCES}

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                "SELECT notification_preferences FROM public.user_settings WHERE user_id = $1",
                user_id,
            )
        if row and row["notification_preferences"]:
            prefs = row["notification_preferences"]
            if isinstance(prefs, str):
                prefs = json.loads(prefs)
            # Merge with defaults so new keys always appear
            merged = {**DEFAULT_NOTIFICATION_PREFERENCES, **prefs}
            return {"preferences": merged}
        return {"preferences": DEFAULT_NOTIFICATION_PREFERENCES}
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error fetching preferences: %s", e)
        raise error_response(500, "Failed to fetch notification preferences", code="DB_ERROR")


@router.put("/preferences", summary="Update notification preferences")
async def update_notification_preferences(
    req: NotificationPreferencesUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update the current user's notification preferences (partial merge)."""
    if not db_configured():
        return {"preferences": DEFAULT_NOTIFICATION_PREFERENCES}

    # Build the update dict from non-None fields
    updates: dict[str, Any] = {}
    for field_name in NotificationPreferencesUpdate.model_fields:
        val = getattr(req, field_name)
        if val is not None:
            updates[field_name] = val

    if not updates:
        raise error_response(400, "No preference fields provided", code="VALIDATION_ERROR")

    try:
        async with get_conn() as conn:
            # Atomic upsert + merge in a single statement
            row = await conn.fetchrow(
                """
                INSERT INTO public.user_settings (user_id, notification_preferences)
                VALUES ($1, $2::jsonb)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    notification_preferences = COALESCE(public.user_settings.notification_preferences, '{}'::jsonb) || $2::jsonb,
                    updated_at = now()
                RETURNING notification_preferences
                """,
                user_id,
                json.dumps(updates),
            )
        prefs = row["notification_preferences"] if row else {}
        if isinstance(prefs, str):
            prefs = json.loads(prefs)
        merged = {**DEFAULT_NOTIFICATION_PREFERENCES, **prefs}
        return {"preferences": merged}
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error updating preferences: %s", e)
        raise error_response(500, "Failed to update notification preferences", code="DB_ERROR")


# ---------------------------------------------------------------------------
# Notification History
# ---------------------------------------------------------------------------


@router.get("/history", summary="Get notification history", description="Returns paginated notification history with unread count for badge display. Supports cursor-based pagination via `cursor` param, or offset-based via `offset`.")
async def get_notification_history(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    cursor: Optional[str] = Query(default=None, description="Cursor for keyset pagination (base64-encoded created_at|id)"),
    unread_only: bool = Query(default=False),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_history_read_limit),
):
    """Return paginated notification history for the current user, newest first."""
    import base64
    from datetime import datetime

    if not db_configured():
        return {"notifications": [], "total_count": 0, "unread_count": 0, "next_cursor": None, "has_more": False}

    await _ensure_table()

    fetch_limit = limit + 1  # one extra to detect has_more

    try:
        async with get_conn() as conn:
            # Unread count (always useful for badge)
            unread_count = await conn.fetchval(
                "SELECT COUNT(*) FROM notification_history WHERE user_id = $1 AND read_at IS NULL",
                user_id,
            )

            # Build base WHERE clause
            base_where = "user_id = $1"
            if unread_only:
                base_where += " AND read_at IS NULL"

            # Cursor-based pagination (preferred for large datasets)
            if cursor:
                try:
                    decoded = base64.b64decode(cursor).decode("utf-8")
                    cursor_ts, cursor_id = decoded.rsplit("|", 1)
                    cursor_dt = datetime.fromisoformat(cursor_ts)
                except Exception:
                    raise error_response(400, "Invalid cursor", code="INVALID_CURSOR")

                rows = await conn.fetch(
                    f"""
                    SELECT id, type, title, body, data, deep_link, read_at, created_at
                    FROM notification_history
                    WHERE {base_where}
                      AND (created_at, id) < ($2::timestamptz, $3::uuid)
                    ORDER BY created_at DESC, id DESC
                    LIMIT $4
                    """,
                    user_id, cursor_dt, cursor_id, fetch_limit,
                )
            else:
                # Offset-based fallback for backward compatibility
                rows = await conn.fetch(
                    f"""
                    SELECT id, type, title, body, data, deep_link, read_at, created_at
                    FROM notification_history
                    WHERE {base_where}
                    ORDER BY created_at DESC, id DESC
                    LIMIT $2 OFFSET $3
                    """,
                    user_id,
                    fetch_limit,
                    offset,
                )

            # Total count for the selected filter
            total_count = await conn.fetchval(
                f"SELECT COUNT(*) FROM notification_history WHERE {base_where}",
                user_id,
            )

        has_more = len(rows) > limit
        result_rows = rows[:limit]

        notifications = []
        for r in result_rows:
            notifications.append({
                "id": str(r["id"]),
                "type": r["type"],
                "title": r["title"],
                "body": r["body"],
                "data": r["data"] if r["data"] else {},
                "deep_link": r["deep_link"],
                "read_at": r["read_at"].isoformat() if r["read_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            })

        # Build next cursor from last row
        next_cursor = None
        if has_more and result_rows:
            last = result_rows[-1]
            ts = last["created_at"].isoformat() if last["created_at"] else ""
            raw = f"{ts}|{last['id']}"
            next_cursor = base64.b64encode(raw.encode("utf-8")).decode("ascii")

        return {
            "notifications": notifications,
            "total_count": total_count or 0,
            "unread_count": unread_count or 0,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error fetching history: %s", e)
        raise error_response(500, "Failed to fetch notification history", code=ErrorCode.DB_ERROR)


@router.patch("/{notification_id}/read", summary="Mark notification as read")
async def mark_notification_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_mark_read_limit),
):
    """Mark a single notification as read. Ownership check enforced via user_id filter."""
    # Validate UUID format before hitting DB
    try:
        import uuid as _uuid
        _uuid.UUID(notification_id)
    except ValueError:
        raise error_response(400, "Invalid notification_id format", code=ErrorCode.VALIDATION_ERROR)

    if not db_configured():
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    await _ensure_table()

    try:
        async with get_conn() as conn:
            result = await conn.execute(
                """
                UPDATE notification_history
                SET read_at = now()
                WHERE id = $1 AND user_id = $2 AND read_at IS NULL
                """,
                notification_id,
                user_id,
            )

        # asyncpg returns "UPDATE N" where N is the number of affected rows
        affected = int(result.split()[-1]) if result else 0
        if affected == 0:
            # Either notification doesn't exist, doesn't belong to user, or already read
            # Check if it exists at all for the user
            async with get_conn() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM notification_history WHERE id = $1 AND user_id = $2",
                    notification_id,
                    user_id,
                )
            if not exists:
                raise error_response(404, "Notification not found", code=ErrorCode.NOT_FOUND)
            # Already read — return 200 (idempotent)
            return {"ok": True, "already_read": True}

        return {"ok": True}
    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error marking notification read: %s", e)
        raise error_response(500, "Failed to mark notification as read", code=ErrorCode.DB_ERROR)


@router.post("/mark-all-read", summary="Mark all notifications as read")
async def mark_all_notifications_read(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_mark_read_limit),
):
    """Mark all unread notifications as read for the current user."""
    if not db_configured():
        return {"updated_count": 0}

    await _ensure_table()

    try:
        async with get_conn() as conn:
            result = await conn.execute(
                """
                UPDATE notification_history
                SET read_at = now()
                WHERE user_id = $1 AND read_at IS NULL
                """,
                user_id,
            )

        updated_count = int(result.split()[-1]) if result else 0
        return {"updated_count": updated_count}
    except asyncpg.PostgresError as e:
        logger.error("[notifications] Error marking all notifications read: %s", e)
        raise error_response(500, "Failed to mark all notifications as read", code=ErrorCode.DB_ERROR)
