"""
Task queue router -- enqueue background tasks and check their status.

Endpoints:
- POST /tasks/enqueue       -- Enqueue a background task
- GET  /tasks/{task_id}/status -- Get status of a background task
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

_task_enqueue_limit = per_user_rate_limit(10, window_seconds=60, scope="task_enqueue")


# ── Request / Response Models ─────────────────────────────────────────────────


class EnqueueTaskInput(BaseModel):
    task_type: str = Field(..., max_length=100)
    payload: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)


class EnqueueTaskResponse(BaseModel):
    task_id: str
    status: str


class TaskStatusResponse(BaseModel):
    id: str
    task_type: str
    status: str
    result: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/enqueue", response_model=EnqueueTaskResponse, status_code=201)
async def enqueue_task(
    body: EnqueueTaskInput,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_task_enqueue_limit),
):
    """Enqueue a background task."""
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            task_id = await conn.fetchval(
                """
                INSERT INTO task_queue (task_type, payload, priority, created_by)
                VALUES ($1, $2::jsonb, $3, $4::uuid)
                RETURNING id
                """,
                body.task_type,
                __import__("json").dumps(body.payload),
                body.priority,
                user_id,
            )

        logger.info(
            "[tasks/enqueue] task_id=%s type=%s user=%s priority=%d",
            task_id, body.task_type, user_id, body.priority,
        )
        return EnqueueTaskResponse(task_id=str(task_id), status="queued")

    except Exception as exc:
        logger.error("[tasks/enqueue] Failed to enqueue task: %s", exc)
        raise error_response(500, "Failed to enqueue task", code="DB_ERROR")


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get status of a background task."""
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise error_response(400, "Invalid task_id format", code="VALIDATION_ERROR")

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, task_type, status, result, error_message,
                       created_at, completed_at
                FROM task_queue
                WHERE id = $1::uuid AND created_by = $2::uuid
                """,
                task_id,
                user_id,
            )

        if not row:
            raise error_response(404, "Task not found", code="NOT_FOUND")

        return TaskStatusResponse(
            id=str(row["id"]),
            task_type=row["task_type"],
            status=row["status"],
            result=row["result"],
            error_message=row["error_message"],
            created_at=row["created_at"].isoformat() if row["created_at"] else "",
            completed_at=row["completed_at"].isoformat() if row["completed_at"] else None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[tasks/status] Failed to get task status: %s", exc)
        raise error_response(500, "Failed to get task status", code="DB_ERROR")
