"""
Items router — DB-backed with in-memory fallback.

Provides create/list endpoints for items. Also includes batch operations.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.fx_service import convert_to_eur


def _parse_purchased_at(value: Optional[str]) -> Optional[datetime]:
    """Coerce the model's ISO string into the datetime asyncpg requires.

    Accepts both the full timestamp watchlistProvider sends
    ("2024-06-01T12:34:56.000Z") and a bare "YYYY-MM-DD". A naive value is
    pinned to UTC rather than the host timezone -- binding a bare date to a
    timestamptz is what stored purchase dates a day early elsewhere.
    Unparseable input yields None so the row still saves without the date.
    """
    if not value:
        return None
    raw = value.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    parsed: Optional[datetime] = None
    for candidate in (raw, raw[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue
    if parsed is None:
        logger.warning("[items] unparseable purchased_at %r, saving without it", value)
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
from app.rate_limit import per_user_rate_limit

router = APIRouter(tags=["Items"])
logger = logging.getLogger(__name__)

# Score floor for accepting a catalog match. /catalog/match documents
# >= 0.75 = strong. A WRONG canonical_key is worse than none: it prices the item
# as a different product and looks authoritative while being silently incorrect.
_CANONICAL_MATCH_FLOOR = 0.75


async def _resolve_canonical_key(title, category, pool):
    """
    Best-effort catalog match -> BARE canonical_key, or None.

    canonical_key is BARE (`sm10-sm10-101`), never namespaced -- CLAUDE.md
    "Identifier formats". The trigger derives canonical_ref from it; never set
    canonical_ref by hand.

    Never raises: a failed match must not fail item creation. The item is saved
    unpriced, exactly as it was before this existed.
    """
    if not title or not category or pool is None:
        return None
    try:
        from app.agents.intake.catalog_matching import _match_catalog_items

        matches = await _match_catalog_items(
            category_id=category,
            suggested_name=title,
            search_keywords=[],
            brand=None,
            set_code=None,
            pool=pool,
            extracted_attributes=None,
        )
    except Exception as e:
        logger.warning("[items] catalog match failed for %r: %s", title, e)
        return None
    if not matches:
        return None
    best = matches[0]
    if float(best.get("match_score") or 0.0) < _CANONICAL_MATCH_FLOOR:
        return None
    return best.get("item_key") or None



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
    # What the user actually paid. Added 2026-07-24: the wishlist "I Got It!"
    # flow (src/data/providers/watchlistProvider.ts:228) has always POSTed
    # `purchase_price`, but this model never declared it, so Pydantic dropped
    # it silently and the INSERT below never stored it — the app prompts for
    # the real acquisition price "to feed the ML model" and then discarded it.
    # Every reader of items.purchase_price (analytics Cost Basis / DCA,
    # the value-saved banner, dossier, CSV export) saw NULL as a result.
    purchase_price: Optional[float] = None
    purchase_currency: Optional[str] = Field(None, max_length=8)
    # ISO date. Written to BOTH purchased_at (timestamptz, read by the
    # analytics DCA series) and purchase_date (date, read by the CSV export)
    # because the schema carries both and different consumers read each.
    purchased_at: Optional[str] = None


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


async def write_quick_valuation(conn, item_id: str, user_id: str, canonical_ref: Optional[str]) -> bool:
    """Best-effort: write a `quick_predictions` row from the catalog market
    valuation so the item card shows a real value right after add.

    Source is `price_prediction_daily.q50`, which is EUR — valuation_worker
    predicts on COALESCE(price_eur, price) with an `_MAX_SANE_PRICE_EUR` bound —
    so it maps directly onto `quick_predictions.q50_eur`. No-op (returns False)
    when the item isn't catalog-linked or has no daily price; the card then
    falls back to the user's own estimate. Never raises — a valuation must not
    block or fail an add.

    Takes the **namespaced** ref (`category:item_key`, i.e. `items.canonical_ref`),
    NOT the bare `canonical_key`. Every `price_prediction_daily.item_ref` is
    namespaced — 0 bare rows — so passing the bare key silently matched nothing
    and this returned False on every add since the column was introduced. See
    docs/schema-lock.md and the 2026-07-25 keyspace audit.
    """
    if not canonical_ref:
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
            canonical_ref,
        )
        if not row or row["q50"] is None:
            return False
        await conn.execute(
            """
            INSERT INTO public.quick_predictions (item_id, user_id, nk, q50_eur, confidence, raw)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
            """,
            item_id, user_id, canonical_ref, float(row["q50"]),
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

    # Resolve canonical_key server-side when the client omits it. Without it the
    # item can never be priced: canonical_key --trg_items_canonical_ref-->
    # canonical_ref --join--> price_predictions.item_ref. The item saves fine and
    # shows "—" forever, with no error and nothing logged.
    #
    # This is the CHOKEPOINT, deliberately. Three separate callers had already
    # been missed one at a time -- /intake/save (barcode+ISBN), import_router
    # (Excel/CSV), and QuickScan's BATCH save in quickscan.tsx, which omits
    # canonicalKey while the single-scan path in useItemDetail.ts passes it.
    # Fixing callers one by one does not converge; resolving here covers every
    # client, including builds already in the field that can never be updated.
    #
    # A client-supplied key always wins: it came from an interactive catalog
    # match the user could see and correct.
    if pool is not None and not payload.canonical_key:
        payload.canonical_key = await _resolve_canonical_key(
            payload.name, payload.category, pool
        )

    # items carries BOTH purchase_price (raw, in purchase_currency) and
    # purchase_price_eur (FX-normalized). The analytics Cost Basis / DCA series
    # sums the EUR half. add-manual.tsx got this on 2026-07-24; this route and
    # import_router.py did not, so table-wide `purchase_price_eur` was non-null
    # on 0 of 5 priced rows and the card could never populate.
    purchase_price_eur = (
        await convert_to_eur(payload.purchase_price, payload.purchase_currency or "EUR")
        if payload.purchase_price is not None
        else None
    )

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                item_id = str(uuid4())
                await conn.execute(
                    """
                    -- purchase_date is deliberately NOT listed: binding one
                    -- param to both `$N::timestamptz` and `$N::date` made
                    -- Postgres infer a date/timestamp type for it, and asyncpg
                    -- then rejected the ISO *string* the model declares --
                    -- "expected a datetime.date or datetime.datetime
                    -- instance, got 'str'". Every POST /items carrying a
                    -- purchased_at 500'd, which is the whole of the watchlist
                    -- "I Got It!" conversion. Bind a real datetime and let
                    -- trg_items_sync_paired_columns derive purchase_date.
                    INSERT INTO items (id, user_id, name, title, category, notes, collection_name, estimated_value, canonical_key,
                                       image_url, brand, condition, year, series, edition_label, attrs,
                                       purchase_price, purchase_price_eur, purchase_currency, purchased_at)
                    VALUES ($1, $2::uuid, $3, $3, $4, $5, $6, $7, $8,
                            $9, $10, $11, $12, $13, $14, $15::jsonb,
                            $16, $17, $18, $19)
                    """,
                    item_id, user_id, payload.name, payload.category, payload.notes,
                    payload.collection_name, payload.estimated_value, payload.canonical_key,
                    payload.image_url, payload.brand, payload.condition, payload.year,
                    payload.series, payload.edition_label,
                    json.dumps(payload.attrs) if payload.attrs else None,
                    payload.purchase_price, purchase_price_eur,
                    payload.purchase_currency, _parse_purchased_at(payload.purchased_at),
                )
                logger.info(
                    "[items] Created item: id=%s, user=%s, canonical_key=%s",
                    item_id, user_id, payload.canonical_key or "(none)",
                )

                # Award XP for adding item (best-effort)
                try:
                    from app.features.gamification_router import record_activity_xp
                    item_count = await conn.fetchval(
                        # archived-exempt: collector milestones are LIFETIME,
                        # matching intake_router's scan milestones. Filtering
                        # here would make the two counters disagree.
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
                # Namespaced ref — mirrors the items.canonical_ref generated column.
                _ref = (
                    f"{payload.category}:{payload.canonical_key}"
                    if payload.canonical_key and payload.category else None
                )
                await write_quick_valuation(conn, item_id, user_id, _ref)

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
            "SELECT canonical_ref FROM items WHERE id = $1::uuid AND user_id = $2::uuid",
            item_id, user_id,
        )
        if not row:
            raise error_response(404, "Item not found")
        valued = await write_quick_valuation(conn, item_id, user_id, row["canonical_ref"])
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
                        WHERE user_id = $1::uuid AND NOT archived
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
                        WHERE user_id = $1::uuid AND NOT archived
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
                # The DICT, not json.dumps(dict). `app/db.py` registers a jsonb
                # codec, so a pre-serialised string is encoded TWICE and lands
                # as a JSON string scalar — and `||` then CONCATENATES instead
                # of merging, turning attrs into an array. That is how this
                # item's attrs became
                # `[{...}, "{\"set_code\": \"\"}", "{\"value_choice\": \"mine\"}"]`
                # and rendered as raw JSON rows on the item screen.
                # The codec now tolerates both, but the call site should still
                # be right — see `_jsonb_encoder` for the full writeup.
                user_id, item_id, merged,
            )
            logger.info("[items] Updated attributes for item=%s, user=%s", item_id, user_id)
            return {"ok": True, "item_id": item_id}
    except Exception as e:
        logger.error("[items] DB error updating attributes: %s", e)
        raise error_response(500, "Failed to update attributes", code="DB_ERROR")


# ---- Update purchase price (the cost-basis capture path) ----
#
# WHY THIS ENDPOINT EXISTS (2026-08-26)
# -------------------------------------
# A purchase price could only ever be entered at CREATION (`add-manual.tsx`).
# The item screen has no field for it, so a member who added an item without one
# could never add it afterwards. Measured on prod: **7 of 108 items** carry a
# purchase price. Everything downstream that says "gain" is built on cost basis,
# and `/portfolio/items` falls back to the earliest PREDICTION when there is no
# purchase price — so for ~93% of the collection the "profit" is model drift.
# That is the root cause of the analytics screen being unable to answer an
# investment question, and it is a capture gap, not an analytics one.
#
# WHY IT IS A SERVER ROUTE AND NOT A CLIENT PATCH
# -----------------------------------------------
# The obvious fix — add `purchase_price` to the `supabase.from('items').update()`
# in `useItemDetail.onSaveEdits` — is a currency bug waiting to happen.
# `items` carries BOTH `purchase_price` (raw, in `purchase_currency`) and
# `purchase_price_eur` (FX-normalised), and every EUR reader sums the second.
# `trg_items_sync_paired_columns` derives the missing half, but ONLY for the
# identity case, and its guard is:
#
#     COALESCE(UPPER(BTRIM(NEW.purchase_currency)), 'EUR') = 'EUR'
#
# A NULL currency is therefore treated as EUR. A client patch that writes
# `purchase_price` without `purchase_currency` would have the database copy a
# JPY amount straight into `purchase_price_eur` — the ~170x error this repo has
# already shipped once, from this exact column pair. The database cannot call
# the FX service; docs/ARCHITECTURE.md says so and says conversion is app-side.
#
# So the price is converted HERE, with `convert_to_eur`, and BOTH halves plus
# the currency are written explicitly. The trigger's identity branch then has
# nothing left to guess at.


class UpdateItemPurchaseRequest(BaseModel):
    """`purchase_price = None` CLEARS the cost basis (both halves)."""
    purchase_price: Optional[float] = Field(None, ge=0)
    # Defaulted, never inferred. The whole point of this endpoint is that the
    # currency travels WITH the amount.
    purchase_currency: str = Field("EUR", pattern=r"^[A-Za-z]{3}$")
    purchased_at: Optional[str] = None
    # Tax, inbound shipping, grading submission -- what a member paid to ACQUIRE
    # the item beyond the sticker price. In `purchase_currency`, the SAME
    # currency as purchase_price: a fee in one currency and a price in another
    # is not a thing this endpoint accepts, because it is not a thing a single
    # purchase is. docs/COLLECTOR_DEMAND.md §5.
    acquisition_fees: Optional[float] = Field(None, ge=0)


@router.patch(
    "/items/{item_id}/purchase",
    dependencies=[Depends(_items_write_limit)],
    summary="Set or clear an item's purchase price",
    description=(
        "Writes purchase_price (raw), purchase_price_eur (FX-normalised) and "
        "purchase_currency together. Send purchase_price=null to clear."
    ),
)
async def update_item_purchase(
    item_id: str,
    payload: UpdateItemPurchaseRequest,
    user_id: str = Depends(get_current_user_id),
):
    pool = get_db_pool()
    if pool is None:
        return {"ok": True, "item_id": item_id}

    currency = payload.purchase_currency.upper()
    price = payload.purchase_price
    # Clearing sets BOTH halves to NULL. Nulling only the raw half would leave a
    # stale EUR figure behind that every analytics reader still sums — the
    # column pair has to move together in both directions.
    price_eur = await convert_to_eur(price, currency) if price is not None else None
    # Fees are a SECOND pair with the same contract, converted with the same
    # currency in the same call. Not left to trg_items_sync_paired_columns: that
    # trigger's guard reads `COALESCE(UPPER(BTRIM(purchase_currency)),'EUR')`,
    # so a NULL currency is treated AS EUR and a JPY amount lands in the euro
    # column (~170x). Converting here means the trigger has nothing to infer.
    fees = payload.acquisition_fees
    fees_eur = await convert_to_eur(fees, currency) if fees is not None else None
    # OMITTED is not the same as NULL, and conflating them was a live
    # regression (caught by audit before release, 2026-08-31). A nullable field
    # with a default cannot express "leave it alone" on its own; only
    # `model_fields_set` can. Applied to BOTH fields:
    #
    #   * fees -- the shipped app sends only `purchase_price`, so an
    #     unconditional write would have nulled fees on every price edit.
    #   * price -- so a member can edit FEES ALONE without the client resending
    #     an unchanged amount. Resending it is not harmless: the server
    #     re-converts through convert_to_eur at TODAY'S rate, so a non-EUR cost
    #     basis would drift a little every time an unrelated field was saved.
    #     `useItemDetail` already refuses to resend an unchanged price for that
    #     reason; this makes the route able to honour it.
    #
    # Explicit null still CLEARS -- that semantic is unchanged and documented on
    # the request model. Omission is the new, third state.
    price_provided = "purchase_price" in payload.model_fields_set
    clearing = price_provided and price is None
    fees_provided = ("acquisition_fees" in payload.model_fields_set) or clearing
    # Clearing the PRICE clears the fees too, whether or not the caller
    # mentioned them: fees on a purchase with no price are an orphan number that
    # portfolio_router would add to a model estimate. Coherence of the ROW, not
    # of the payload.
    if clearing:
        fees, fees_eur = None, None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE items
                   SET purchase_price       = CASE WHEN $10 THEN $3 ELSE purchase_price     END,
                       purchase_price_eur   = CASE WHEN $10 THEN $4 ELSE purchase_price_eur END,
                       purchase_currency    = CASE WHEN $10 THEN $5 ELSE purchase_currency  END,
                       purchased_at         = COALESCE($6::timestamptz, purchased_at),
                       -- $9 = "the caller addressed fees at all". Without it
                       -- an omitted field is indistinguishable from an
                       -- explicit null and every price-only edit wipes them.
                       acquisition_fees     = CASE WHEN $9 THEN $7 ELSE acquisition_fees     END,
                       acquisition_fees_eur = CASE WHEN $9 THEN $8 ELSE acquisition_fees_eur END,
                       updated_at           = NOW()
                 WHERE id = $2::uuid AND user_id = $1::uuid
             RETURNING id, purchase_price, purchase_price_eur, purchase_currency,
                       acquisition_fees, acquisition_fees_eur
                """,
                user_id, item_id, price, price_eur, currency, payload.purchased_at,
                fees, fees_eur, fees_provided, price_provided,
            )
            if row is None:
                # Not found OR not theirs — one message for both, so the
                # endpoint cannot be used to probe which item ids exist.
                raise error_response(404, "Item not found", code="NOT_FOUND")

            logger.info(
                "[items] purchase set item=%s user=%s price=%s fees=%s %s -> EUR %s / %s",
                item_id, user_id, price, fees, currency, price_eur, fees_eur,
            )
            return {
                "ok": True,
                "item_id": str(row["id"]),
                "purchase_price": float(row["purchase_price"]) if row["purchase_price"] is not None else None,
                "purchase_price_eur": float(row["purchase_price_eur"]) if row["purchase_price_eur"] is not None else None,
                "purchase_currency": row["purchase_currency"],
                "acquisition_fees": float(row["acquisition_fees"]) if row["acquisition_fees"] is not None else None,
                "acquisition_fees_eur": float(row["acquisition_fees_eur"]) if row["acquisition_fees_eur"] is not None else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[items] DB error updating purchase price: %s", e)
        raise error_response(500, "Failed to update purchase price", code="DB_ERROR")
