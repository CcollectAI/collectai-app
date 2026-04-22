"""
Catalog Browser Router.

Public endpoints for browsing the category_items catalog:
  GET /catalog/{category_id}/items  — paginated, searchable catalog browse

Progress tracking (authenticated):
  PATCH /items/{item_id}/progress   — update progress_status, progress_pct, progress_notes
  GET   /items/{item_id}/progress   — get progress for an item
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_pool
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Catalog Browser"])

# Note: browse_catalog_items is public (no auth) and protected by the global
# IP-based rate limit middleware. per_user_rate_limit is used only on
# authenticated endpoints below.
_catalog_progress_limit = per_user_rate_limit(60, window_seconds=60, scope="catalog_progress")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CatalogItem(BaseModel):
    id: str
    category: str
    item_key: str
    title: str
    brand: Optional[str] = None
    rarity: Optional[str] = None
    notes: Optional[str] = None
    has_reference_image: bool = False  # R50k: image_url kept backend-only for intake/QuickScan matching
    external_id: Optional[str] = None
    set_code: Optional[str] = None
    estimated_price: Optional[float] = None


class CatalogBrowseResponse(BaseModel):
    items: list[CatalogItem]
    total: int
    limit: int
    offset: int
    category_id: str


class ProgressUpdateRequest(BaseModel):
    progress_status: Optional[str] = Field(
        None,
        pattern=r"^(unread|reading|read|unplayed|playing|played|completed)$",
    )
    progress_pct: Optional[int] = Field(None, ge=0, le=100)
    progress_notes: Optional[str] = Field(None, max_length=2000)


class ProgressResponse(BaseModel):
    item_id: str
    progress_status: Optional[str] = None
    progress_pct: Optional[int] = None
    progress_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /catalog/{category_id}/items — browse catalog items
# ---------------------------------------------------------------------------

@router.get(
    "/catalog/{category_id}/items",
    response_model=CatalogBrowseResponse,
)
async def browse_catalog_items(
    category_id: str,
    q: Optional[str] = Query(None, max_length=200, description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    rarity: Optional[str] = Query(None, description="Filter by rarity tier"),
):
    """Browse items in the category_items catalog for a given category."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # Build query conditions
    conditions = ["category = $1"]
    params: list[Any] = [category_id]
    idx = 2

    if q and q.strip():
        conditions.append(f"title ILIKE ${idx}")
        params.append(f"%{q.strip()}%")
        idx += 1

    if rarity and rarity.strip():
        conditions.append(f"rarity = ${idx}")
        params.append(rarity.strip())
        idx += 1

    where = " AND ".join(conditions)

    # Count total matching
    total = await pool.fetchval(
        f"SELECT count(*) FROM category_items WHERE {where}",
        *params,
    ) or 0

    # Fetch page
    rows = await pool.fetch(
        f"""
        SELECT id, category, item_key, title, brand, rarity, notes,
               image_url, external_id, set_code
        FROM category_items
        WHERE {where}
        ORDER BY title ASC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
        limit,
        offset,
    )

    # Try to fetch estimated prices from price_predictions or market_observations
    item_keys = [r["item_key"] for r in rows]
    price_map: dict[str, float] = {}
    if item_keys:
        try:
            price_rows = await pool.fetch(
                """
                -- market_observations is vestigial (1 row at audit time);
                -- market_hits is the canonical comp source (~900K rows).
                -- 2026-04-22 drift sweep redirected to use it. item_ref on
                -- market_hits has the canonical `category:key` prefix, so
                -- match against ci.item_ref (which already has the prefix)
                -- with a fallback to category:item_key.
                SELECT ci.item_key, mp.price_eur AS price
                FROM category_items ci
                JOIN LATERAL (
                    SELECT price_eur FROM market_hits mh
                    WHERE mh.item_ref = ci.item_ref
                       OR mh.item_ref = (ci.category || ':' || ci.item_key)
                    ORDER BY mh.seen_at DESC
                    LIMIT 1
                ) mp ON TRUE
                WHERE ci.item_key = ANY($1)
                """,
                item_keys,
            )
            for pr in price_rows:
                price_map[pr["item_key"]] = float(pr["price"])
        except Exception as exc:
            logger.debug("Could not fetch estimated prices: %s", exc)

    items = [
        CatalogItem(
            id=str(r["id"]),
            category=r["category"],
            item_key=r["item_key"],
            title=r["title"],
            brand=r["brand"],
            rarity=r["rarity"],
            notes=r["notes"],
            has_reference_image=bool(r["image_url"]),
            external_id=r["external_id"],
            set_code=r["set_code"],
            estimated_price=price_map.get(r["item_key"]),
        )
        for r in rows
    ]

    # Record demand signal (best-effort; no user_id/geo — public endpoint)
    try:
        from app.features.data_moat import record_demand_signal
        await record_demand_signal(
            signal_type="catalog_browsed",
            category=category_id,
            query_text=q,
        )
    except Exception as e:
        logger.debug("[catalog_browser] demand signal recording failed: %s", e)

    return CatalogBrowseResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        category_id=category_id,
    )


# ---------------------------------------------------------------------------
# PATCH /items/{item_id}/progress — update progress tracking
# ---------------------------------------------------------------------------

@router.patch(
    "/items/{item_id}/progress",
    response_model=ProgressResponse,
)
async def update_item_progress(
    item_id: str,
    req: ProgressUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_catalog_progress_limit),
):
    """Update reading/play progress for an item owned by the current user."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # Verify item belongs to user
    owner = await pool.fetchval(
        "SELECT user_id FROM items WHERE id = $1::uuid",
        item_id,
    )
    if not owner:
        raise error_response(404, "Item not found", code="NOT_FOUND")
    if str(owner) != user_id:
        raise error_response(403, "Not your item", code="FORBIDDEN")

    # Build SET clause
    sets: list[str] = []
    params: list[Any] = []
    idx = 1

    if req.progress_status is not None:
        sets.append(f"progress_status = ${idx}")
        params.append(req.progress_status)
        idx += 1
    if req.progress_pct is not None:
        sets.append(f"progress_pct = ${idx}")
        params.append(req.progress_pct)
        idx += 1
    if req.progress_notes is not None:
        sets.append(f"progress_notes = ${idx}")
        params.append(req.progress_notes)
        idx += 1

    if not sets:
        raise error_response(400, "No fields to update", code="VALIDATION_ERROR")

    sets.append(f"updated_at = now()")

    await pool.execute(
        f"UPDATE items SET {', '.join(sets)} WHERE id = ${idx}::uuid AND user_id = ${idx + 1}::uuid",
        *params,
        item_id,
        user_id,
    )

    # Fetch updated values
    row = await pool.fetchrow(
        "SELECT progress_status, progress_pct, progress_notes FROM items WHERE id = $1::uuid",
        item_id,
    )

    return ProgressResponse(
        item_id=item_id,
        progress_status=row["progress_status"] if row else None,
        progress_pct=row["progress_pct"] if row else None,
        progress_notes=row["progress_notes"] if row else None,
    )


# ---------------------------------------------------------------------------
# GET /items/{item_id}/progress — get progress for an item
# ---------------------------------------------------------------------------

@router.get(
    "/items/{item_id}/progress",
    response_model=ProgressResponse,
)
async def get_item_progress(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get reading/play progress for an item owned by the current user."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    row = await pool.fetchrow(
        "SELECT user_id, progress_status, progress_pct, progress_notes FROM items WHERE id = $1::uuid",
        item_id,
    )
    if not row:
        raise error_response(404, "Item not found", code="NOT_FOUND")
    if str(row["user_id"]) != user_id:
        raise error_response(403, "Not your item", code="FORBIDDEN")

    return ProgressResponse(
        item_id=item_id,
        progress_status=row["progress_status"],
        progress_pct=row["progress_pct"],
        progress_notes=row["progress_notes"],
    )
