"""
Activity feed router — log and retrieve user activities.

Endpoints:
- GET  /activity/{user_id}  — Get activity feed for a user
- POST /activity/log         — Log a new activity
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/activity", tags=["activity"])

_activity_log_limit = per_user_rate_limit(30, window_seconds=60, scope="activity_log")
logger = logging.getLogger(__name__)


class LogActivityInput(BaseModel):
    activity_type: str = Field(..., max_length=100)
    title: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=1000)
    metadata: dict = Field(default_factory=dict)
    is_public: bool = True


@router.get("/{user_id}")
async def get_user_activity(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get activity feed for a user."""
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise error_response(400, "Invalid user_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, user_id, activity_type, title, description,
                          metadata, is_public, created_at
                   FROM activity_feed
                   WHERE user_id = $1::uuid AND is_public = true
                   ORDER BY created_at DESC
                   LIMIT $2 OFFSET $3""",
                user_id,
                limit,
                offset,
            )
            activities = [dict(r) for r in rows] if rows else []
            # Convert UUIDs and datetimes to strings
            for a in activities:
                for k, v in a.items():
                    if hasattr(v, "isoformat"):
                        a[k] = v.isoformat()
                    elif hasattr(v, "hex"):
                        a[k] = str(v)
            return {"activities": activities}
    except Exception as e:
        logger.warning("get_user_activity error: %s", e)
        raise error_response(500, "Failed to fetch activity feed")


@router.post("/log")
async def log_activity(
    body: LogActivityInput,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_activity_log_limit),
):
    """Log an activity to the user's feed."""
    pool = get_db_pool()
    if not pool:
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        import json

        async with pool.acquire() as conn:
            result = await conn.fetchval(
                """INSERT INTO activity_feed
                       (user_id, activity_type, title, description, metadata, is_public)
                   VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6)
                   RETURNING id""",
                user_id,
                body.activity_type,
                body.title,
                body.description,
                json.dumps(body.metadata),
                body.is_public,
            )
            return {"id": str(result) if result else None, "success": True}
    except Exception as e:
        logger.warning("log_activity error: %s", e)
        raise error_response(500, "Failed to log activity")
