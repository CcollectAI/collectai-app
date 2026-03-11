"""
Items router — DB-backed with in-memory fallback.

Provides create/list endpoints for items. Also includes batch operations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(tags=["Items"])
logger = logging.getLogger(__name__)

# Per-user: 50 requests per minute for reading items
_items_read_limit = per_user_rate_limit(50, scope="items_read")
# Per-user: 10 requests per minute for creating items
_items_write_limit = per_user_rate_limit(10, scope="items_write")


# ---- Models ----

class ItemCreateRequest(BaseModel):
    name: str = Field(..., max_length=500)
    category: Optional[str] = Field(None, max_length=64)
    collection_name: Optional[str] = Field(None, max_length=255)
    estimated_value: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=5000)


class ItemResponse(ItemCreateRequest):
    id: str


class BatchArchiveRequest(BaseModel):
    item_ids: List[str] = Field(..., min_length=1, max_length=100)


class BatchDeleteRequest(BaseModel):
    item_ids: List[str] = Field(..., min_length=1, max_length=100)


class BatchResponse(BaseModel):
    success: bool
    affected_count: int


class PaginatedItemsResponse(BaseModel):
    items: List[ItemResponse]
    next_cursor: Optional[str] = None
    has_more: bool = False


# ---- In-memory fallback store ----

_DEMO_ITEMS: list[ItemResponse] = []


def get_demo_items() -> list[ItemResponse]:
    """Accessor for the in-memory demo items list (used by portfolio router)."""
    return _DEMO_ITEMS


# ---- Endpoints ----

@router.post("/items", response_model=ItemResponse, dependencies=[Depends(_items_write_limit)], summary="Create a new item")
async def create_item(
    payload: ItemCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new item in the user's collection."""
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                item_id = str(uuid4())
                await conn.execute(
                    """
                    INSERT INTO items (id, user_id, title, category, notes, collection_name, estimated_value)
                    VALUES ($1, $2::uuid, $3, $4, $5, $6, $7)
                    """,
                    item_id, user_id, payload.name, payload.category, payload.notes,
                    payload.collection_name, payload.estimated_value,
                )
                logger.info("[items] Created item: id=%s, user=%s", item_id, user_id)

                # Award XP for adding item (best-effort)
                try:
                    from app.features.gamification_router import record_activity_xp
                    item_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM items WHERE user_id = $1::uuid",
                        user_id,
                    )
                    achievement_checks = []
                    milestones = [
                        (5, "collector_5"), (10, "collector_10"),
                        (25, "collector_25"), (50, "collector_50"),
                        (100, "collector_100"),
                    ]
                    for threshold, ach_id in milestones:
                        if item_count >= threshold:
                            achievement_checks.append((ach_id, item_count))
                    await record_activity_xp(conn, user_id, 10, achievement_checks or None)
                except Exception:
                    logger.debug("[items] Gamification XP award failed (non-critical)")

                return ItemResponse(
                    id=item_id,
                    name=payload.name,
                    category=payload.category,
                    collection_name=payload.collection_name,
                    estimated_value=payload.estimated_value,
                    notes=payload.notes,
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[items] DB error creating item: %s", e)
            raise error_response(500, "Failed to create item", code="DB_ERROR")

    # In-memory fallback
    new_id = f"demo-{len(_DEMO_ITEMS) + 1}"
    item = ItemResponse(
        id=new_id,
        name=payload.name,
        category=payload.category,
        collection_name=payload.collection_name,
        estimated_value=payload.estimated_value,
        notes=payload.notes,
    )
    _DEMO_ITEMS.append(item)
    return item


@router.get("/items", response_model=PaginatedItemsResponse, dependencies=[Depends(_items_read_limit)], summary="List user items", description="Returns paginated items for the authenticated user, ordered by most recently updated. Supports cursor-based pagination via `cursor` and `limit` query params.")
async def list_items(
    user_id: str = Depends(get_current_user_id),
    limit: int = 50,
    cursor: Optional[str] = None,
):
    """List items in the user's collection with cursor-based pagination."""
    import base64
    from datetime import datetime

    # Clamp limit to [1, 200]
    limit = max(1, min(limit, 200))
    fetch_limit = limit + 1  # fetch one extra to detect has_more

    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # Decode cursor: base64-encoded "updated_at|id"
                if cursor:
                    try:
                        decoded = base64.b64decode(cursor).decode("utf-8")
                        cursor_ts, cursor_id = decoded.rsplit("|", 1)
                        cursor_dt = datetime.fromisoformat(cursor_ts)
                    except Exception:
                        raise error_response(400, "Invalid cursor", code="INVALID_CURSOR")

                    rows = await conn.fetch(
                        """
                        SELECT id, title, category, notes, collection_name, estimated_value, updated_at
                        FROM items
                        WHERE user_id = $1::uuid
                          AND (updated_at, id) < ($2::timestamptz, $3::uuid)
                        ORDER BY updated_at DESC, id DESC
                        LIMIT $4
                        """,
                        user_id, cursor_dt, cursor_id, fetch_limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id, title, category, notes, collection_name, estimated_value, updated_at
                        FROM items
                        WHERE user_id = $1::uuid
                        ORDER BY updated_at DESC, id DESC
                        LIMIT $2
                        """,
                        user_id, fetch_limit,
                    )

                has_more = len(rows) > limit
                result_rows = rows[:limit]

                items = [
                    ItemResponse(
                        id=str(r["id"]),
                        name=r["title"] or "Untitled",
                        category=r["category"],
                        collection_name=r.get("collection_name"),
                        estimated_value=float(r["estimated_value"]) if r.get("estimated_value") is not None else None,
                        notes=r["notes"],
                    )
                    for r in result_rows
                ]

                next_cursor = None
                if has_more and result_rows:
                    last = result_rows[-1]
                    ts = last["updated_at"].isoformat() if last["updated_at"] else ""
                    raw = f"{ts}|{last['id']}"
                    next_cursor = base64.b64encode(raw.encode("utf-8")).decode("ascii")

                return PaginatedItemsResponse(
                    items=items,
                    next_cursor=next_cursor,
                    has_more=has_more,
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[items] DB error listing items: %s", e)
            raise error_response(500, "Failed to list items", code="DB_ERROR")

    # In-memory fallback
    return PaginatedItemsResponse(items=_DEMO_ITEMS, next_cursor=None, has_more=False)


@router.post("/items/batch-archive", response_model=BatchResponse, summary="Archive multiple items")
async def batch_archive_items(
    request: BatchArchiveRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Archive multiple items at once."""
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE items
                    SET attributes_json = COALESCE(attributes_json, '{}'::jsonb) || '{"_archived": true}'::jsonb
                    WHERE id = ANY($1::uuid[])
                      AND user_id = $2::uuid
                    """,
                    request.item_ids, user_id,
                )
                count = int(result.split()[-1]) if result else 0
                logger.info("[items] Batch archived %d items for user=%s", count, user_id)
                return BatchResponse(success=True, affected_count=count)
        except Exception as e:
            logger.error("[items] DB error batch archiving: %s", e)
            raise error_response(500, "Failed to batch archive", code="DB_ERROR")

    # In-memory fallback — remove from demo items
    before = len(_DEMO_ITEMS)
    ids_set = set(request.item_ids)
    remaining = [it for it in _DEMO_ITEMS if it.id not in ids_set]
    _DEMO_ITEMS.clear()
    _DEMO_ITEMS.extend(remaining)
    return BatchResponse(success=True, affected_count=before - len(_DEMO_ITEMS))


@router.post("/items/batch-delete", response_model=BatchResponse, summary="Delete multiple items")
async def batch_delete_items(
    request: BatchDeleteRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Delete multiple items at once."""
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM items
                    WHERE id = ANY($1::uuid[])
                      AND user_id = $2::uuid
                    """,
                    request.item_ids, user_id,
                )
                count = int(result.split()[-1]) if result else 0
                logger.info("[items] Batch deleted %d items for user=%s", count, user_id)
                return BatchResponse(success=True, affected_count=count)
        except Exception as e:
            logger.error("[items] DB error batch deleting: %s", e)
            raise error_response(500, "Failed to batch delete", code="DB_ERROR")

    # In-memory fallback
    before = len(_DEMO_ITEMS)
    ids_set = set(request.item_ids)
    remaining = [it for it in _DEMO_ITEMS if it.id not in ids_set]
    _DEMO_ITEMS.clear()
    _DEMO_ITEMS.extend(remaining)
    return BatchResponse(success=True, affected_count=before - len(_DEMO_ITEMS))


# ---- Update item attributes / size ----

class UpdateItemAttributesRequest(BaseModel):
    attributes: Dict[str, Any] = Field(default_factory=dict)
    item_size: Optional[str] = None
    size_system: Optional[str] = Field(None, pattern=r"^(us|eu|uk|cm|mm)$")


@router.patch("/items/{item_id}/attributes", summary="Update item attributes", description="Merge additional attributes into the item's attributes_json and optionally set size fields.")
async def update_item_attributes(
    item_id: str,
    payload: UpdateItemAttributesRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Merge attributes_json and optionally set item_size/size_system."""
    pool = get_db_pool()

    if pool is None:
        return {"ok": True, "item_id": item_id}

    try:
        async with pool.acquire() as conn:
            # Build SET clauses dynamically
            set_parts = []
            params: list = [user_id, item_id]
            idx = 3  # next placeholder index

            if payload.attributes:
                set_parts.append(
                    f"attributes_json = COALESCE(attributes_json, '{{}}'::jsonb) || ${idx}::jsonb"
                )
                params.append(json.dumps(payload.attributes))
                idx += 1

            if payload.item_size is not None:
                set_parts.append(f"item_size = ${idx}")
                params.append(payload.item_size)
                idx += 1

            if payload.size_system is not None:
                set_parts.append(f"size_system = ${idx}")
                params.append(payload.size_system)
                idx += 1

            if not set_parts:
                return {"ok": True, "item_id": item_id}

            set_parts.append("updated_at = NOW()")

            query = f"""
                UPDATE items
                SET {', '.join(set_parts)}
                WHERE id = $2::uuid AND user_id = $1::uuid
            """
            await conn.execute(query, *params)
            logger.info("[items] Updated attributes for item=%s, user=%s", item_id, user_id)
            return {"ok": True, "item_id": item_id}
    except Exception as e:
        logger.error("[items] DB error updating attributes: %s", e)
        raise error_response(500, "Failed to update attributes", code="DB_ERROR")
