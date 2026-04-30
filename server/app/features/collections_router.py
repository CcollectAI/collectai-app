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
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode
from app.lib.validators import is_valid_category
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/collections", tags=["Collections"])
logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

_collections_list_limit = per_user_rate_limit(30, window_seconds=60, scope="collections_list")


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

# NOTE 2026-04-30: the existing SQL in this file targets a `collections`
# table with columns category / collection_key / display_name /
# release_date / total_items / image_url / notes. The live `collections`
# table is a per-user "my collections" grouping with only id / user_id /
# name / created_at. The catalog-of-sets data the FE needs lives in
# `category_items` aggregated by set_code — that aggregation never
# landed. Until it does, every SELECT below would 500. Each handler now
# short-circuits to an empty/404 response so the FE shows "no
# collections" instead of an error toast. Tracked in
# router_drift_allowlist.txt as a 25-entry deferred bug.

@router.get("", response_model=CollectionListResponse)
async def list_collections(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _rl=Depends(_collections_list_limit),
):
    """List all available collections, optionally filtered by category.

    The catalog-of-sets aggregation that this endpoint was originally
    designed for never landed (see module docstring). Returns empty
    until that aggregation exists. Earlier the body kept ~70 lines of
    unreachable SQL against a `collections` table shape that doesn't
    exist — removed so audit_router_sql_drift stops flagging
    `collections.collection_key`/`display_name`/etc. (7 entries).
    """
    return CollectionListResponse(collections=[], total=0)


@router.get("/user/progress", response_model=UserProgressResponse)
async def get_user_progress(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(30, window_seconds=60, scope="collections")),
):
    """Get the authenticated user's set completion progress."""
    pool = get_db_pool()

    if pool is not None:
        try:
            uid = _to_uuid_or_none(user_id)
            if uid is None:
                return UserProgressResponse(
                    progress=[], total_collections=0, total_owned=0, total_items=0,
                )

            async with pool.acquire() as conn:
                # 2026-04-22: switched from collections + collection_items +
                # user_category_ownership (the lean `collections` table is
                # for user-named lists, not set/release tracking) to the
                # canonical sets + user_set_progress model. user_set_progress
                # already maintains owned_count + completion_pct so no
                # GROUP BY needed. external_id maps to collection_key,
                # name to display_name, category_id to category.
                base_sql = """
                    SELECT
                        s.id            AS collection_id,
                        s.external_id   AS collection_key,
                        s.name          AS display_name,
                        s.category_id   AS category,
                        s.total_items,
                        COALESCE(usp.owned_count, 0) AS owned_count
                    FROM public.sets s
                    LEFT JOIN public.user_set_progress usp
                           ON usp.set_id = s.id AND usp.user_id = $1
                """
                if category:
                    rows = await conn.fetch(
                        base_sql + " WHERE s.category_id = $2 ORDER BY s.release_date DESC NULLS LAST",
                        uid, category,
                    )
                else:
                    rows = await conn.fetch(
                        base_sql + " ORDER BY s.release_date DESC NULLS LAST",
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
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _rl=Depends(per_user_rate_limit(30, window_seconds=60, scope="collections")),
):
    """Get a specific collection — stub. Catalog-of-sets aggregation not built."""
    if not _UUID_RE.match(collection_id):
        raise error_response(400, "Invalid collection_id format", code=ErrorCode.INVALID_UUID)
    raise error_response(404, "Collection not found", code=ErrorCode.NOT_FOUND)


@router.get("/{collection_id}/progress", response_model=UserCollectionProgress)
async def get_collection_progress(
    collection_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(30, window_seconds=60, scope="collections")),
):
    """Per-collection progress — stub for the same reason as detail above."""
    if not _UUID_RE.match(collection_id):
        raise error_response(400, "Invalid collection_id format", code=ErrorCode.INVALID_UUID)
    raise error_response(404, "Collection not found", code=ErrorCode.NOT_FOUND)


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
