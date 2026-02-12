"""
Push notification management router.

Endpoints:
- POST /notifications/register   — Register an Expo push token
- DELETE /notifications/register  — Unregister a push token
- GET  /notifications/tokens      — List active tokens for current user
"""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import db_configured, get_conn
from app.errors import error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
                """,
                user_id,
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
