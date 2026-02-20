"""
Collections router for set/collection completion tracking.

Endpoints:
- GET  /collections                           - List all collections (optionally filtered by category)
- GET  /collections/{collection_id}           - Get collection detail + items
- GET  /collections/user/progress             - Get user's completion progress across all collections
- GET  /collections/{collection_id}/progress  - Get user's progress for a specific collection
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response

router = APIRouter(prefix="/collections", tags=["collections"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except (ImportError, RuntimeError, OSError):
        return None


# ---------------------------------------------------------------------------
# In-memory fallback store (when DB is disabled)
# ---------------------------------------------------------------------------

_mem_collections: list[dict] = []
_mem_collection_items: list[dict] = []


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CollectionSummary(BaseModel):
    id: str
    category: str
    collection_key: str
    display_name: str
    release_date: Optional[str] = None
    total_items: int = 0
    image_url: Optional[str] = None
    notes: Optional[str] = None


class CollectionListResponse(BaseModel):
    collections: list[CollectionSummary]
    total: int


class CollectionItemInfo(BaseModel):
    item_key: str
    title: str
    sequence_number: Optional[int] = None
    image_url: Optional[str] = None
    owned: bool = False


class CollectionDetail(BaseModel):
    id: str
    category: str
    collection_key: str
    display_name: str
    release_date: Optional[str] = None
    total_items: int = 0
    image_url: Optional[str] = None
    notes: Optional[str] = None
    items: list[CollectionItemInfo] = Field(default_factory=list)


class UserCollectionProgress(BaseModel):
    collection_id: str
    collection_key: str
    display_name: str
    category: str
    total_items: int = 0
    owned_count: int = 0
    completion_pct: float = 0.0
    missing_items: list[str] = Field(default_factory=list)


class UserProgressResponse(BaseModel):
    progress: list[UserCollectionProgress]
    total_collections: int = 0
    total_owned: int = 0
    total_items: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=CollectionListResponse)
async def list_collections(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all available collections, optionally filtered by category."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                if category:
                    rows = await conn.fetch(
                        """
                        SELECT id, category, collection_key, display_name,
                               release_date::text, total_items, image_url, notes
                        FROM public.collections
                        WHERE category = $1
                        ORDER BY release_date DESC NULLS LAST
                        LIMIT $2 OFFSET $3
                        """,
                        category, limit, offset,
                    )
                    count_row = await conn.fetchrow(
                        "SELECT count(*) AS cnt FROM public.collections WHERE category = $1",
                        category,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id, category, collection_key, display_name,
                               release_date::text, total_items, image_url, notes
                        FROM public.collections
                        ORDER BY release_date DESC NULLS LAST
                        LIMIT $1 OFFSET $2
                        """,
                        limit, offset,
                    )
                    count_row = await conn.fetchrow(
                        "SELECT count(*) AS cnt FROM public.collections"
                    )
                total = count_row["cnt"] if count_row else 0
                items = [CollectionSummary(**dict(r)) for r in rows]
                return CollectionListResponse(collections=items, total=total)
        except Exception as exc:
            logger.error("Failed to list collections: %s", exc)
            raise error_response(500, "Failed to list collections")

    # In-memory fallback
    filtered = _mem_collections
    if category:
        filtered = [c for c in filtered if c.get("category") == category]
    total = len(filtered)
    page = filtered[offset:offset + limit]
    return CollectionListResponse(
        collections=[CollectionSummary(**c) for c in page],
        total=total,
    )


@router.get("/user/progress", response_model=UserProgressResponse)
async def get_user_progress(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    user_id: str = Depends(get_current_user_id),
):
    """Get the authenticated user's set completion progress."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            uid = _to_uuid_or_none(user_id)
            if uid is None:
                return UserProgressResponse(
                    progress=[], total_collections=0, total_owned=0, total_items=0,
                )

            async with pool.acquire() as conn:
                if category:
                    rows = await conn.fetch(
                        """
                        SELECT
                            c.id AS collection_id,
                            c.collection_key,
                            c.display_name,
                            c.category,
                            c.total_items,
                            count(uco.id) AS owned_count
                        FROM public.collections c
                        LEFT JOIN public.collection_items ci ON ci.collection_id = c.id
                        LEFT JOIN public.user_category_ownership uco
                            ON uco.category_item_id = ci.category_item_id
                            AND uco.user_id = $1
                        WHERE c.category = $2
                        GROUP BY c.id
                        ORDER BY c.release_date DESC NULLS LAST
                        """,
                        uid, category,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT
                            c.id AS collection_id,
                            c.collection_key,
                            c.display_name,
                            c.category,
                            c.total_items,
                            count(uco.id) AS owned_count
                        FROM public.collections c
                        LEFT JOIN public.collection_items ci ON ci.collection_id = c.id
                        LEFT JOIN public.user_category_ownership uco
                            ON uco.category_item_id = ci.category_item_id
                            AND uco.user_id = $1
                        GROUP BY c.id
                        ORDER BY c.release_date DESC NULLS LAST
                        """,
                        uid,
                    )

                progress = []
                total_owned = 0
                total_items = 0
                for r in rows:
                    owned = int(r["owned_count"])
                    total = int(r["total_items"]) if r["total_items"] else 0
                    pct = round(100.0 * owned / total, 1) if total > 0 else 0.0
                    total_owned += owned
                    total_items += total
                    progress.append(UserCollectionProgress(
                        collection_id=str(r["collection_id"]),
                        collection_key=r["collection_key"],
                        display_name=r["display_name"],
                        category=r["category"],
                        total_items=total,
                        owned_count=owned,
                        completion_pct=pct,
                    ))

                return UserProgressResponse(
                    progress=progress,
                    total_collections=len(progress),
                    total_owned=total_owned,
                    total_items=total_items,
                )
        except Exception as exc:
            logger.error("Failed to get user progress: %s", exc)
            raise error_response(500, "Failed to get collection progress")

    # In-memory fallback
    return UserProgressResponse(progress=[], total_collections=0, total_owned=0, total_items=0)


@router.get("/{collection_id}", response_model=CollectionDetail)
async def get_collection_detail(
    collection_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a specific collection with its items and user ownership status."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            cid = _to_uuid_or_none(collection_id)
            if cid is None:
                raise error_response(404, "Collection not found", code="NOT_FOUND")

            uid = _to_uuid_or_none(user_id)

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, category, collection_key, display_name,
                           release_date::text, total_items, image_url, notes
                    FROM public.collections
                    WHERE id = $1
                    """,
                    cid,
                )
                if not row:
                    raise error_response(404, "Collection not found", code="NOT_FOUND")

                if uid is not None:
                    item_rows = await conn.fetch(
                        """
                        SELECT
                            ci2.item_key,
                            ci2.title,
                            ci.sequence_number,
                            ci2.image_url,
                            CASE WHEN uco.id IS NOT NULL THEN true ELSE false END AS owned
                        FROM public.collection_items ci
                        JOIN public.category_items ci2 ON ci2.id = ci.category_item_id
                        LEFT JOIN public.user_category_ownership uco
                            ON uco.category_item_id = ci.category_item_id
                            AND uco.user_id = $1
                        WHERE ci.collection_id = $2
                        ORDER BY ci.sequence_number ASC NULLS LAST, ci2.title ASC
                        """,
                        uid, cid,
                    )
                else:
                    item_rows = await conn.fetch(
                        """
                        SELECT
                            ci2.item_key,
                            ci2.title,
                            ci.sequence_number,
                            ci2.image_url,
                            false AS owned
                        FROM public.collection_items ci
                        JOIN public.category_items ci2 ON ci2.id = ci.category_item_id
                        WHERE ci.collection_id = $1
                        ORDER BY ci.sequence_number ASC NULLS LAST, ci2.title ASC
                        """,
                        cid,
                    )

                items = [
                    CollectionItemInfo(
                        item_key=ir["item_key"],
                        title=ir["title"],
                        sequence_number=ir["sequence_number"],
                        image_url=ir["image_url"],
                        owned=ir["owned"],
                    )
                    for ir in item_rows
                ]

                return CollectionDetail(**dict(row), items=items)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to get collection detail: %s", exc)
            raise error_response(500, "Failed to get collection detail")

    # In-memory fallback
    for c in _mem_collections:
        if c.get("id") == collection_id:
            return CollectionDetail(**c, items=[])
    raise error_response(404, "Collection not found", code="NOT_FOUND")


@router.get("/{collection_id}/progress", response_model=UserCollectionProgress)
async def get_collection_progress(
    collection_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get user's completion progress for a specific collection, including missing items."""
    pool = _get_db_pool()

    if pool is not None:
        try:
            cid = _to_uuid_or_none(collection_id)
            if cid is None:
                raise error_response(404, "Collection not found", code="NOT_FOUND")

            uid = _to_uuid_or_none(user_id)
            if uid is None:
                raise error_response(404, "Collection not found", code="NOT_FOUND")

            async with pool.acquire() as conn:
                coll = await conn.fetchrow(
                    """
                    SELECT id, collection_key, display_name, category, total_items
                    FROM public.collections WHERE id = $1
                    """,
                    cid,
                )
                if not coll:
                    raise error_response(404, "Collection not found", code="NOT_FOUND")

                missing_rows = await conn.fetch(
                    """
                    SELECT ci2.title
                    FROM public.collection_items ci
                    JOIN public.category_items ci2 ON ci2.id = ci.category_item_id
                    LEFT JOIN public.user_category_ownership uco
                        ON uco.category_item_id = ci.category_item_id
                        AND uco.user_id = $1
                    WHERE ci.collection_id = $2
                      AND uco.id IS NULL
                    ORDER BY ci.sequence_number ASC NULLS LAST
                    """,
                    uid, cid,
                )
                missing = [r["title"] for r in missing_rows]

                owned_row = await conn.fetchrow(
                    """
                    SELECT count(*) AS cnt
                    FROM public.collection_items ci
                    JOIN public.user_category_ownership uco
                        ON uco.category_item_id = ci.category_item_id
                        AND uco.user_id = $1
                    WHERE ci.collection_id = $2
                    """,
                    uid, cid,
                )
                owned = int(owned_row["cnt"]) if owned_row else 0
                total = int(coll["total_items"]) if coll["total_items"] else 0
                pct = round(100.0 * owned / total, 1) if total > 0 else 0.0

                return UserCollectionProgress(
                    collection_id=str(coll["id"]),
                    collection_key=coll["collection_key"],
                    display_name=coll["display_name"],
                    category=coll["category"],
                    total_items=total,
                    owned_count=owned,
                    completion_pct=pct,
                    missing_items=missing[:100],
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to get collection progress: %s", exc)
            raise error_response(500, "Failed to get collection progress")

    raise error_response(404, "Collection not found", code="NOT_FOUND")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_uuid(s: str) -> bool:
    try:
        UUID(s)
        return True
    except (ValueError, AttributeError):
        return False


def _to_uuid_or_none(s: str | None) -> UUID | None:
    """Convert string to UUID, returning None if invalid."""
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, AttributeError):
        return None
