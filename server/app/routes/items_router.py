"""
Items router — DB-backed with in-memory fallback.

Provides create/list endpoints for items. Also includes batch operations.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
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
    # Catalog-match key from QuickScan / intake (passed as catalog_match_key
    # in the intake response). Stored as items.canonical_key — the JOIN key
    # that links a user's item to the catalog's price_predictions /
    # price_history / valuation pipelines. Without this, every Premium
    # surface that JOINs items → catalog returns empty for paid users.
    # Format example: 'pokemon:base-set-charizard-4-102'.
    canonical_key: Optional[str] = Field(None, max_length=255)
    # Rich detail — populated by QuickScan / catalog-match / manual form so the
    # item lands as a FULL card (ItemAttributesSection reads `attrs`; the card
    # shows `image_url`). Before this, POST /items dropped all of it and every
    # non-ISBN add landed with empty attrs + no image.
    image_url: Optional[str] = Field(None, max_length=1000)
    brand: Optional[str] = Field(None, max_length=128)
    condition: Optional[str] = Field(None, max_length=64)
    year: Optional[int] = None
    series: Optional[str] = Field(None, max_length=255)
    edition_label: Optional[str] = Field(None, max_length=128)
    # Category-specific attributes (rarity, set_code, edition, print run,
    # authenticity, etc.) — stored as items.attrs (jsonb object).
    attrs: Optional[Dict[str, Any]] = None


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


async def write_quick_valuation(conn, item_id: str, user_id: str, canonical_key: Optional[str]) -> bool:
    """Best-effort: write a `quick_predictions` row from the catalog market
    valuation so the item card shows a real value right after add.

    Source is `price_prediction_daily.q50`, which is EUR — valuation_worker
    predicts on COALESCE(price_eur, price) with an `_MAX_SANE_PRICE_EUR` bound —
    so it maps directly onto `quick_predictions.q50_eur`. No-op (returns False)
    when the item isn't catalog-linked or has no daily price; the card then
    falls back to the user's own estimate. Never raises — a valuation must not
    block or fail an add.
    """
    if not canonical_key:
        return False
    try:
        row = await conn.fetchrow(
            """
            SELECT q50, confidence, model_version
            FROM public.price_prediction_daily
            WHERE item_ref = $1 AND q50 IS NOT NULL
            ORDER BY day DESC
            LIMIT 1
            """,
            canonical_key,
        )
        if not row or row["q50"] is None:
            return False
        await conn.execute(
            """
            INSERT INTO public.quick_predictions (item_id, user_id, nk, q50_eur, confidence, raw)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
            """,
            item_id, user_id, canonical_key, float(row["q50"]),
            float(row["confidence"]) if row["confidence"] is not None else 0.6,
            json.dumps({"source": "catalog_daily", "model_version": row["model_version"]}),
        )
        return True
    except Exception:
        logger.debug("[items] quick valuation write skipped (non-critical)")
        return False


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
                    INSERT INTO items (id, user_id, title, category, notes, collection_name, estimated_value, canonical_key,
                                       image_url, brand, condition, year, series, edition_label, attrs)
                    VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8,
                            $9, $10, $11, $12, $13, $14, $15::jsonb)
                    """,
                    item_id, user_id, payload.name, payload.category, payload.notes,
                    payload.collection_name, payload.estimated_value, payload.canonical_key,
                    payload.image_url, payload.brand, payload.condition, payload.year,
                    payload.series, payload.edition_label,
                    json.dumps(payload.attrs) if payload.attrs else None,
                )
                logger.info(
                    "[items] Created item: id=%s, user=%s, canonical_key=%s",
                    item_id, user_id, payload.canonical_key or "(none)",
                )

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

                # Market valuation for the card (best-effort, EUR, local data).
                await write_quick_valuation(conn, item_id, user_id, payload.canonical_key)

                return ItemResponse(id=item_id, **payload.model_dump())
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[items] DB error creating item: %s", e)
            raise error_response(500, "Failed to create item", code="DB_ERROR")

    # In-memory fallback
    new_id = f"demo-{len(_DEMO_ITEMS) + 1}"
    item = ItemResponse(id=new_id, **payload.model_dump())
    _DEMO_ITEMS.append(item)
    return item


@router.post("/items/{item_id}/revalue", dependencies=[Depends(_items_write_limit)], summary="Compute the card valuation for an item")
async def revalue_item(item_id: str, user_id: str = Depends(get_current_user_id)):
    """Write a fresh quick_predictions row from the catalog market valuation.

    The manual-add screen inserts items client-side (direct Supabase), so it
    can't run the server-side valuation inline the way POST /items does. It
    calls this right after saving so a catalog-linked item shows a value on its
    card immediately. No-op (valued=false) when the item isn't catalog-linked.
    """
    pool = get_db_pool()
    if pool is None:
        return {"ok": False, "valued": False}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT canonical_key FROM items WHERE id = $1::uuid AND user_id = $2::uuid",
            item_id, user_id,
        )
        if not row:
            raise error_response(404, "Item not found")
        valued = await write_quick_valuation(conn, item_id, user_id, row["canonical_key"])
    return {"ok": True, "valued": valued}


@router.get("/items", response_model=PaginatedItemsResponse, dependencies=[Depends(_items_read_limit)], summary="List user items", description="Returns paginated items for the authenticated user, ordered by most recently updated. Supports cursor-based pagination via `cursor` and `limit` query params.")
async def list_items(
    user_id: str = Depends(get_current_user_id),
    limit: int = 50,
    cursor: Optional[str] = None,
):
    """List items in the user's collection with cursor-based pagination."""
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
                        SELECT id, title, category, notes, collection_name, estimated_value, canonical_key, updated_at
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
                        SELECT id, title, category, notes, collection_name, estimated_value, canonical_key, updated_at
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
                        canonical_key=r.get("canonical_key"),
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
                # items has a dedicated `archived` boolean column.
                # Earlier path stuffed _archived:true into a non-existent
                # `attributes_json` jsonb; UPDATE returned 0 every time.
                result = await conn.execute(
                    """
                    UPDATE items
                    SET archived = true
                    WHERE id = ANY($1::uuid[])
                      AND user_id = $2::uuid
                    """,
                    request.item_ids, user_id,
                )
                count = int(result.split()[-1]) if result else 0
                logger.info("[items] Batch archived %d items for user=%s", count, user_id)
            try:
                from app.features.data_moat import record_demand_signal
                for iid in request.item_ids[:50]:  # cap to avoid hammering on bulk archives
                    await record_demand_signal(
                        signal_type="item_archived",
                        item_key=iid,
                        user_id=user_id,
                    )
            except Exception:
                pass
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
            # Regret signal — items deleted shortly after add suggest the
            # vision/category recommendation was wrong. Feed model retraining.
            try:
                from app.features.data_moat import record_demand_signal
                for iid in request.item_ids[:50]:
                    await record_demand_signal(
                        signal_type="item_deleted",
                        item_key=iid,
                        user_id=user_id,
                    )
            except Exception:
                pass
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


@router.patch("/items/{item_id}/attributes", summary="Update item attributes", description="Merge additional attributes into the item's attrs jsonb. Size fields are folded into the same jsonb under item_size / size_system keys.")
async def update_item_attributes(
    item_id: str,
    payload: UpdateItemAttributesRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Merge into items.attrs (jsonb). The items table has no dedicated
    item_size / size_system columns — they live in the attrs jsonb so
    callers can read them back with attrs->>'item_size' etc."""
    pool = get_db_pool()

    if pool is None:
        return {"ok": True, "item_id": item_id}

    merged: Dict[str, Any] = dict(payload.attributes or {})
    if payload.item_size is not None:
        merged["item_size"] = payload.item_size
    if payload.size_system is not None:
        merged["size_system"] = payload.size_system

    if not merged:
        return {"ok": True, "item_id": item_id}

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE items
                SET attrs = COALESCE(attrs, '{}'::jsonb) || $3::jsonb,
                    updated_at = NOW()
                WHERE id = $2::uuid AND user_id = $1::uuid
                """,
                user_id, item_id, json.dumps(merged),
            )
            logger.info("[items] Updated attributes for item=%s, user=%s", item_id, user_id)
            return {"ok": True, "item_id": item_id}
    except Exception as e:
        logger.error("[items] DB error updating attributes: %s", e)
        raise error_response(500, "Failed to update attributes", code="DB_ERROR")
