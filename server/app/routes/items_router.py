"""
Items router — DB-backed with in-memory fallback.

Provides create/list endpoints for items. Also includes batch operations.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response

router = APIRouter(tags=["items"])
logger = logging.getLogger(__name__)


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


# ---- DB helper ----

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug("DB pool not available: %s", e)
        return None


# ---- In-memory fallback store ----

_DEMO_ITEMS: list[ItemResponse] = []


def get_demo_items() -> list[ItemResponse]:
    """Accessor for the in-memory demo items list (used by portfolio router)."""
    return _DEMO_ITEMS


# ---- Endpoints ----

@router.post("/items", response_model=ItemResponse)
async def create_item(
    payload: ItemCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new item in the user's collection."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                item_id = str(uuid4())
                await conn.execute(
                    """
                    INSERT INTO items (id, user_id, title, category, notes)
                    VALUES ($1, $2::uuid, $3, $4, $5)
                    """,
                    item_id, user_id, payload.name, payload.category, payload.notes,
                )
                logger.info("[items] Created item: id=%s, user=%s", item_id, user_id)
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


@router.get("/items", response_model=list[ItemResponse])
async def list_items(user_id: str = Depends(get_current_user_id)):
    """List items in the user's collection."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, title, category, notes
                    FROM items
                    WHERE user_id = $1::uuid
                    ORDER BY updated_at DESC
                    LIMIT 200
                    """,
                    user_id,
                )
                return [
                    ItemResponse(
                        id=str(r["id"]),
                        name=r["title"] or "Untitled",
                        category=r["category"],
                        notes=r["notes"],
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.error("[items] DB error listing items: %s", e)
            raise error_response(500, "Failed to list items", code="DB_ERROR")

    # In-memory fallback
    return _DEMO_ITEMS


@router.post("/items/batch-archive", response_model=BatchResponse)
async def batch_archive_items(
    request: BatchArchiveRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Archive multiple items at once."""
    pool = _get_db_pool()

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


@router.post("/items/batch-delete", response_model=BatchResponse)
async def batch_delete_items(
    request: BatchDeleteRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Delete multiple items at once."""
    pool = _get_db_pool()

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
