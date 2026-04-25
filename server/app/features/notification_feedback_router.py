"""
Notification feedback router — closes the push engagement loop.

Three small endpoints the RN client calls when a notification is delivered,
opened, or leads to a downstream user action. Writes to the existing schema:

- notification_impressions  (push delivered to device)
- notification_interactions (push tapped / dismissed / etc.)
- notification_outcomes     (post-tap action: bought / followed / sold etc.)

Without these writes the entire push-quality feedback loop has no fuel —
the schema existed but no client/router wrote to it (verified 2026-04-25,
all three tables had 0 rows).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/feedback", tags=["Notifications"])

# Per-user 60/min — clients can report multiple per minute on a busy app
_feedback_limit = per_user_rate_limit(60, window_seconds=60, scope="notif_feedback")


class ImpressionRequest(BaseModel):
    notification_id: str
    client_context: Optional[dict[str, Any]] = None


class InteractionRequest(BaseModel):
    notification_id: str
    kind: str = Field(..., max_length=32, description="open|dismiss|action|swipe")
    meta: Optional[dict[str, Any]] = None


class OutcomeRequest(BaseModel):
    notification_id: str
    outcome: str = Field(..., max_length=32, description="converted|ignored|expired|other")
    action_type: Optional[str] = Field(None, max_length=64, description="e.g. bought, followed, sold")
    action_ref: Optional[dict[str, Any]] = None
    latency_seconds: Optional[int] = Field(None, ge=0, le=86_400 * 30)


@router.post("/impression", summary="Record that a push was delivered to the device")
async def record_impression(
    payload: ImpressionRequest,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_feedback_limit),
):
    pool = get_db_pool()
    if pool is None:
        return {"ok": True, "stored": False}
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.notification_impressions
                    (notification_id, user_id, first_seen_at, last_seen_at,
                     seen_count, client_context)
                VALUES ($1::uuid, $2::uuid, NOW(), NOW(), 1, $3::jsonb)
                ON CONFLICT (notification_id, user_id) DO UPDATE
                SET last_seen_at = NOW(),
                    seen_count = public.notification_impressions.seen_count + 1
                """,
                payload.notification_id,
                user_id,
                json.dumps(payload.client_context or {}),
            )
        return {"ok": True, "stored": True}
    except Exception as e:
        logger.warning("[notif_feedback] impression insert failed: %s", e)
        return {"ok": False, "error": str(e)[:120]}


@router.post("/interaction", summary="Record that a user interacted with a push")
async def record_interaction(
    payload: InteractionRequest,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_feedback_limit),
):
    pool = get_db_pool()
    if pool is None:
        return {"ok": True, "stored": False}
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.notification_interactions
                    (notification_id, user_id, kind, occurred_at, meta)
                VALUES ($1::uuid, $2::uuid, $3, NOW(), $4::jsonb)
                """,
                payload.notification_id, user_id, payload.kind,
                json.dumps(payload.meta or {}),
            )
        return {"ok": True, "stored": True}
    except Exception as e:
        logger.warning("[notif_feedback] interaction insert failed: %s", e)
        return {"ok": False, "error": str(e)[:120]}


@router.post("/outcome", summary="Record the downstream outcome of a push")
async def record_outcome(
    payload: OutcomeRequest,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_feedback_limit),
):
    pool = get_db_pool()
    if pool is None:
        return {"ok": True, "stored": False}
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.notification_outcomes
                    (notification_id, user_id, outcome, acted_at,
                     latency_seconds, action_type, action_ref, computed_at)
                VALUES ($1::uuid, $2::uuid, $3, NOW(), $4, $5, $6::jsonb, NOW())
                """,
                payload.notification_id, user_id, payload.outcome,
                payload.latency_seconds, payload.action_type,
                json.dumps(payload.action_ref or {}),
            )
        return {"ok": True, "stored": True}
    except Exception as e:
        logger.warning("[notif_feedback] outcome insert failed: %s", e)
        return {"ok": False, "error": str(e)[:120]}
