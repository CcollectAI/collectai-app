"""
Push notification management router.

Endpoints:
- POST /notifications/register       — Register an Expo push token
- DELETE /notifications/register      — Unregister a push token
- GET  /notifications/tokens          — List active tokens for current user
- GET  /notifications/preferences     — Get notification preferences
- PUT  /notifications/preferences     — Update notification preferences
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
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Per-user: 10 token registrations per hour (prevent push token spam)
_register_token_limit = per_user_rate_limit(10, window_seconds=3600, scope="push_token_register")

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


@router.post("/register")
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


@router.delete("/register")
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


@router.get("/tokens")
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


@router.get("/preferences")
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


@router.put("/preferences")
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
