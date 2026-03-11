"""
Set/collection completion tracking router.

Endpoints:
- GET  /sets                    — List sets, optionally filtered by category
- GET  /sets/{set_id}           — Get set detail with all set_items
- GET  /sets/{set_id}/progress  — Get user's completion progress for a set
- PUT  /sets/{set_id}/progress  — Mark items as owned/unowned
- GET  /sets/my-progress        — List all sets user is tracking with completion %
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import db_configured, get_conn
from app.errors import error_response
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sets", tags=["Sets"])

_set_progress_limit = per_user_rate_limit(30, window_seconds=60, scope="set_progress")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SetSummary(BaseModel):
    id: str
    category_id: str
    name: str
    description: Optional[str] = None
    total_items: int = 0
    release_date: Optional[str] = None
    image_url: Optional[str] = None
    external_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SetItem(BaseModel):
    id: str
    set_id: str
    name: str
    position: Optional[int] = None
    external_id: Optional[str] = None
    image_url: Optional[str] = None
    rarity: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[str] = None


class SetDetail(SetSummary):
    items: List[SetItem] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    user_id: str
    set_id: str
    owned_item_ids: List[str] = Field(default_factory=list)
    owned_count: int = 0
    completion_pct: float = 0.0
    notes: Optional[str] = None
    updated_at: Optional[str] = None


class ProgressUpdateRequest(BaseModel):
    item_ids: List[str] = Field(..., min_length=1, description="UUIDs of set_items to add or remove")
    action: str = Field(..., pattern="^(add|remove)$", description="add or remove")


class MyProgressEntry(BaseModel):
    set_id: str
    set_name: str
    category_id: str
    total_items: int = 0
    image_url: Optional[str] = None
    owned_count: int = 0
    completion_pct: float = 0.0
    notes: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_set_summary(row: asyncpg.Record) -> dict:
    """Convert a DB row to a SetSummary-compatible dict."""
    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return {
        "id": str(row["id"]),
        "category_id": row["category_id"],
        "name": row["name"],
        "description": row.get("description"),
        "total_items": row["total_items"],
        "release_date": row["release_date"].isoformat() if row.get("release_date") else None,
        "image_url": row.get("image_url"),
        "external_id": row.get("external_id"),
        "metadata": meta if meta else {},
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def _row_to_set_item(row: asyncpg.Record) -> dict:
    """Convert a DB row to a SetItem-compatible dict."""
    meta = row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return {
        "id": str(row["id"]),
        "set_id": str(row["set_id"]),
        "name": row["name"],
        "position": row.get("position"),
        "external_id": row.get("external_id"),
        "image_url": row.get("image_url"),
        "rarity": row.get("rarity"),
        "metadata": meta if meta else {},
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def _validate_uuid(value: str, label: str = "id") -> str:
    """Validate a UUID string, raise 400 on invalid."""
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        raise error_response(400, f"Invalid {label}: {value}", code=ErrorCode.INVALID_UUID)


# ---------------------------------------------------------------------------
# GET /sets  — list sets, optionally filtered by category
# ---------------------------------------------------------------------------


@router.get("")
async def list_sets(
    category_id: Optional[str] = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List sets, optionally filtered by category_id."""
    if not db_configured():
        return {"sets": [], "total": 0}

    try:
        async with get_conn() as conn:
            if category_id:
                rows = await conn.fetch(
                    """
                    SELECT id, category_id, name, description, total_items,
                           release_date, image_url, external_id, metadata,
                           created_at, updated_at
                    FROM public.sets
                    WHERE category_id = $1
                    ORDER BY name
                    LIMIT $2 OFFSET $3
                    """,
                    category_id,
                    limit,
                    offset,
                )
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM public.sets WHERE category_id = $1",
                    category_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, category_id, name, description, total_items,
                           release_date, image_url, external_id, metadata,
                           created_at, updated_at
                    FROM public.sets
                    ORDER BY name
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )
                total = await conn.fetchval("SELECT COUNT(*) FROM public.sets")

        return {
            "sets": [_row_to_set_summary(r) for r in rows],
            "total": total,
        }
    except asyncpg.PostgresError as e:
        logger.error("[sets] Error listing sets: %s", e)
        raise error_response(500, "Failed to list sets", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /sets/my-progress  — list all sets user is tracking
# NOTE: must be registered BEFORE /sets/{set_id} to avoid route shadowing
# ---------------------------------------------------------------------------


@router.get("/my-progress")
async def list_my_progress(
    user_id: str = Depends(get_current_user_id),
    category_id: Optional[str] = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all sets the current user is tracking with completion percentages."""
    if not db_configured():
        return {"progress": [], "total": 0}

    try:
        async with get_conn() as conn:
            if category_id:
                rows = await conn.fetch(
                    """
                    SELECT
                        usp.set_id,
                        s.name AS set_name,
                        s.category_id,
                        s.total_items,
                        s.image_url,
                        usp.owned_count,
                        usp.completion_pct,
                        usp.notes,
                        usp.updated_at
                    FROM public.user_set_progress usp
                    JOIN public.sets s ON s.id = usp.set_id
                    WHERE usp.user_id = $1 AND s.category_id = $2
                    ORDER BY usp.updated_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    user_id,
                    category_id,
                    limit,
                    offset,
                )
                total = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM public.user_set_progress usp
                    JOIN public.sets s ON s.id = usp.set_id
                    WHERE usp.user_id = $1 AND s.category_id = $2
                    """,
                    user_id,
                    category_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        usp.set_id,
                        s.name AS set_name,
                        s.category_id,
                        s.total_items,
                        s.image_url,
                        usp.owned_count,
                        usp.completion_pct,
                        usp.notes,
                        usp.updated_at
                    FROM public.user_set_progress usp
                    JOIN public.sets s ON s.id = usp.set_id
                    WHERE usp.user_id = $1
                    ORDER BY usp.updated_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    user_id,
                    limit,
                    offset,
                )
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM public.user_set_progress WHERE user_id = $1",
                    user_id,
                )

        return {
            "progress": [
                {
                    "set_id": str(r["set_id"]),
                    "set_name": r["set_name"],
                    "category_id": r["category_id"],
                    "total_items": r["total_items"],
                    "image_url": r.get("image_url"),
                    "owned_count": r["owned_count"],
                    "completion_pct": float(r["completion_pct"]),
                    "notes": r.get("notes"),
                    "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
                }
                for r in rows
            ],
            "total": total,
        }
    except asyncpg.PostgresError as e:
        logger.error("[sets] Error listing user progress: %s", e)
        raise error_response(500, "Failed to list progress", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /sets/{set_id}  — get set detail with all items
# ---------------------------------------------------------------------------


@router.get("/{set_id}")
async def get_set_detail(set_id: str):
    """Get a set with its full list of set_items."""
    set_id = _validate_uuid(set_id, "set_id")

    if not db_configured():
        raise error_response(404, "Set not found", code=ErrorCode.NOT_FOUND)

    try:
        async with get_conn() as conn:
            set_row = await conn.fetchrow(
                "SELECT id, category_id, name, description, total_items, release_date, image_url, external_id, metadata, created_at, updated_at FROM public.sets WHERE id = $1",
                set_id,
            )
            if not set_row:
                raise error_response(404, "Set not found", code=ErrorCode.NOT_FOUND)

            item_rows = await conn.fetch(
                """
                SELECT id, set_id, name, position, external_id, image_url, rarity, metadata, created_at
                FROM public.set_items
                WHERE set_id = $1
                ORDER BY position ASC NULLS LAST, name ASC
                """,
                set_id,
            )

        result = _row_to_set_summary(set_row)
        result["items"] = [_row_to_set_item(r) for r in item_rows]
        return result
    except asyncpg.PostgresError as e:
        logger.error("[sets] Error fetching set %s: %s", set_id, e)
        raise error_response(500, "Failed to fetch set", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# GET /sets/{set_id}/progress  — get user's completion progress
# ---------------------------------------------------------------------------


@router.get("/{set_id}/progress")
async def get_set_progress(
    set_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get the current user's completion progress for a specific set."""
    set_id = _validate_uuid(set_id, "set_id")

    if not db_configured():
        return {
            "user_id": user_id,
            "set_id": set_id,
            "owned_item_ids": [],
            "owned_count": 0,
            "completion_pct": 0.0,
            "notes": None,
            "updated_at": None,
        }

    try:
        async with get_conn() as conn:
            # Verify the set exists
            set_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM public.sets WHERE id = $1)",
                set_id,
            )
            if not set_exists:
                raise error_response(404, "Set not found", code=ErrorCode.NOT_FOUND)

            row = await conn.fetchrow(
                """
                SELECT user_id, set_id, owned_item_ids, owned_count,
                       completion_pct, notes, updated_at
                FROM public.user_set_progress
                WHERE user_id = $1 AND set_id = $2
                """,
                user_id,
                set_id,
            )

        if not row:
            return {
                "user_id": user_id,
                "set_id": set_id,
                "owned_item_ids": [],
                "owned_count": 0,
                "completion_pct": 0.0,
                "notes": None,
                "updated_at": None,
            }

        return {
            "user_id": str(row["user_id"]),
            "set_id": str(row["set_id"]),
            "owned_item_ids": [str(uid) for uid in (row["owned_item_ids"] or [])],
            "owned_count": row["owned_count"],
            "completion_pct": float(row["completion_pct"]),
            "notes": row.get("notes"),
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        }
    except asyncpg.PostgresError as e:
        logger.error("[sets] Error fetching progress for set %s: %s", set_id, e)
        raise error_response(500, "Failed to fetch progress", code=ErrorCode.DB_ERROR)


# ---------------------------------------------------------------------------
# PUT /sets/{set_id}/progress  — mark items owned/unowned
# ---------------------------------------------------------------------------


@router.put("/{set_id}/progress")
async def update_set_progress(
    set_id: str,
    req: ProgressUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_set_progress_limit),
):
    """Add or remove items from the user's owned list for a set."""
    set_id = _validate_uuid(set_id, "set_id")

    # Validate all provided item_ids
    validated_ids = []
    for item_id in req.item_ids:
        validated_ids.append(_validate_uuid(item_id, "item_id"))

    if not db_configured():
        raise error_response(503, "Database not available", code=ErrorCode.DB_UNAVAILABLE)

    try:
        async with get_conn() as conn:
            # Verify the set exists and get total_items
            set_row = await conn.fetchrow(
                "SELECT id, total_items FROM public.sets WHERE id = $1",
                set_id,
            )
            if not set_row:
                raise error_response(404, "Set not found", code=ErrorCode.NOT_FOUND)

            total_items = set_row["total_items"]

            # Verify all provided item_ids belong to this set
            valid_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM public.set_items
                WHERE set_id = $1 AND id = ANY($2::uuid[])
                """,
                set_id,
                validated_ids,
            )
            if valid_count != len(validated_ids):
                raise error_response(
                    400,
                    "One or more item_ids do not belong to this set",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            # Atomic upsert with array manipulation in SQL to avoid race conditions
            if req.action == "add":
                result_row = await conn.fetchrow(
                    """
                    INSERT INTO public.user_set_progress
                        (user_id, set_id, owned_item_ids, owned_count, completion_pct, updated_at)
                    VALUES (
                        $1, $2, $3::uuid[],
                        cardinality($3::uuid[]),
                        ROUND(cardinality($3::uuid[])::numeric / GREATEST($4, 1) * 100, 2),
                        now()
                    )
                    ON CONFLICT (user_id, set_id)
                    DO UPDATE SET
                        owned_item_ids = (
                            SELECT array_agg(DISTINCT uid)
                            FROM unnest(
                                COALESCE(public.user_set_progress.owned_item_ids, '{}') || $3::uuid[]
                            ) AS uid
                        ),
                        owned_count = (
                            SELECT COUNT(DISTINCT uid)
                            FROM unnest(
                                COALESCE(public.user_set_progress.owned_item_ids, '{}') || $3::uuid[]
                            ) AS uid
                        ),
                        completion_pct = ROUND(
                            (SELECT COUNT(DISTINCT uid) FROM unnest(
                                COALESCE(public.user_set_progress.owned_item_ids, '{}') || $3::uuid[]
                            ) AS uid)::numeric / GREATEST($4, 1) * 100, 2
                        ),
                        updated_at = now()
                    RETURNING owned_item_ids, owned_count, completion_pct
                    """,
                    user_id,
                    set_id,
                    validated_ids,
                    total_items,
                )
            else:
                # Remove: filter out the provided IDs
                result_row = await conn.fetchrow(
                    """
                    INSERT INTO public.user_set_progress
                        (user_id, set_id, owned_item_ids, owned_count, completion_pct, updated_at)
                    VALUES ($1, $2, '{}'::uuid[], 0, 0, now())
                    ON CONFLICT (user_id, set_id)
                    DO UPDATE SET
                        owned_item_ids = (
                            SELECT COALESCE(array_agg(uid), '{}')
                            FROM unnest(COALESCE(public.user_set_progress.owned_item_ids, '{}')) AS uid
                            WHERE uid != ALL($3::uuid[])
                        ),
                        owned_count = (
                            SELECT COUNT(*)
                            FROM unnest(COALESCE(public.user_set_progress.owned_item_ids, '{}')) AS uid
                            WHERE uid != ALL($3::uuid[])
                        ),
                        completion_pct = ROUND(
                            (SELECT COUNT(*) FROM unnest(COALESCE(public.user_set_progress.owned_item_ids, '{}')) AS uid
                             WHERE uid != ALL($3::uuid[])
                            )::numeric / GREATEST($4, 1) * 100, 2
                        ),
                        updated_at = now()
                    RETURNING owned_item_ids, owned_count, completion_pct
                    """,
                    user_id,
                    set_id,
                    validated_ids,
                    total_items,
                )

            owned_list = [str(uid) for uid in (result_row["owned_item_ids"] or [])] if result_row else []
            owned_count = result_row["owned_count"] if result_row else 0
            completion_pct = float(result_row["completion_pct"]) if result_row else 0.0

        logger.info(
            "[sets] Progress updated: user=%s set=%s action=%s items=%d owned=%d/%d (%.1f%%)",
            user_id, set_id, req.action, len(validated_ids), owned_count, total_items, completion_pct,
        )

        return {
            "user_id": user_id,
            "set_id": set_id,
            "owned_item_ids": owned_list,
            "owned_count": owned_count,
            "completion_pct": completion_pct,
            "updated_at": None,  # just updated, client can use local time
        }
    except asyncpg.PostgresError as e:
        logger.error("[sets] Error updating progress for set %s: %s", set_id, e)
        raise error_response(500, "Failed to update progress", code=ErrorCode.DB_ERROR)
