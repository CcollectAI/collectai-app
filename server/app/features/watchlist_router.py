from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

import logging

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

_watchlist_write_limit = per_user_rate_limit(30, window_seconds=60, scope="watchlist_write")
logger = logging.getLogger(__name__)


class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    item_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    predicted_value: Optional[float] = None
    currency: str = "EUR"
    last_market_price: Optional[float] = None
    last_checked_at: Optional[datetime] = None
    price_trend: Optional[str] = None
    market_hit_count: int = 0


class WatchlistCreate(BaseModel):
    item_id: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=64)
    predicted_value: Optional[float] = None
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")


class WatchlistResponse(BaseModel):
    items: List[WatchlistItem]


# In-memory fallback store keyed by user_id (used when DB is unavailable)
_WATCHLIST: dict[str, list[WatchlistItem]] = {}


@router.get("/mine", response_model=WatchlistResponse, summary="List watchlist items")
async def get_my_watchlist(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> WatchlistResponse:
    limit, offset = pagination
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                # 2026-04-22: switched from legacy `watchlist` (bigint id /
                # query / nk / est_value — wrong shape) to watchlist_items
                # (the modern RLS-protected table). Routes SELECT/INSERT
                # both use title as the display field; the 4 router-only
                # columns (item_id / predicted_value / price_trend /
                # market_hit_count) were added by migration 20260422.
                rows = await conn.fetch(
                    """
                    SELECT id, user_id::text AS user_id, item_id,
                           title AS name, category,
                           created_at, predicted_value, currency,
                           last_market_price, last_checked_at,
                           price_trend, market_hit_count
                    FROM public.watchlist_items
                    WHERE user_id = $1::uuid
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    user_id, limit, offset,
                )
                items = [
                    WatchlistItem(
                        id=str(r["id"]),
                        user_id=r["user_id"],
                        item_id=r["item_id"],
                        name=r["name"],
                        category=r["category"],
                        created_at=r["created_at"],
                        predicted_value=float(r["predicted_value"]) if r["predicted_value"] else None,
                        currency=r["currency"] or "EUR",
                        last_market_price=float(r["last_market_price"]) if r["last_market_price"] else None,
                        last_checked_at=r["last_checked_at"],
                        price_trend=r["price_trend"],
                        market_hit_count=r["market_hit_count"] or 0,
                    )
                    for r in rows
                ]
                return WatchlistResponse(items=items)
        except Exception as e:
            logger.error("[watchlist] DB error listing watchlist: %s", e)
            raise error_response(500, "Failed to list watchlist", code="DB_ERROR")

    # In-memory fallback
    items = _WATCHLIST.get(user_id, [])
    return WatchlistResponse(items=items[offset:offset + limit])


@router.post("/mine", response_model=WatchlistItem, summary="Add item to watchlist")
async def add_to_watchlist(payload: WatchlistCreate, user_id: str = Depends(get_current_user_id), _rl=Depends(_watchlist_write_limit)) -> WatchlistItem:
    pool = get_db_pool()

    item = WatchlistItem(
        user_id=user_id,
        item_id=payload.item_id,
        name=payload.name,
        category=payload.category,
        predicted_value=payload.predicted_value,
        currency=payload.currency,
    )

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO public.watchlist_items
                        (id, user_id, item_id, title, category,
                         created_at, predicted_value, currency)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8)
                    """,
                    item.id, user_id, payload.item_id,
                    # watchlist_items.title is NOT NULL — fallback keeps INSERTs valid
                    # even if the mobile client sends an empty name field.
                    payload.name or "(unnamed)",
                    payload.category, item.created_at,
                    payload.predicted_value, payload.currency,
                )
                logger.info("[watchlist] Added item: id=%s, user=%s", item.id, user_id)

                # Record demand signal with geo enrichment (best-effort)
                try:
                    from app.features.data_moat import record_demand_signal, get_user_geo
                    region, country = await get_user_geo(user_id)
                    await record_demand_signal(
                        signal_type="watchlist_add",
                        category=payload.category,
                        item_key=payload.name or payload.item_id,
                        user_id=user_id,
                        region=region,
                        country_code=country,
                    )
                except Exception as e:
                    logger.debug("[watchlist] demand signal recording failed: %s", e)

                return item
        except Exception as e:
            logger.error("[watchlist] DB error adding to watchlist: %s", e)
            raise error_response(500, "Failed to add to watchlist", code="DB_ERROR")

    # In-memory fallback
    _WATCHLIST.setdefault(user_id, []).append(item)
    return item


@router.delete("/mine/{watch_id}", response_model=WatchlistResponse, summary="Remove from watchlist")
async def remove_from_watchlist(watch_id: str, user_id: str = Depends(get_current_user_id), _rl=Depends(_watchlist_write_limit)) -> WatchlistResponse:
    pool = get_db_pool()

    if pool is not None:
        try:
            removed_meta = None
            async with pool.acquire() as conn:
                # Capture the row before delete so we can record category +
                # title in the demand_signal (negative cancellation signal).
                removed_meta = await conn.fetchrow(
                    "SELECT category, title, item_id FROM public.watchlist_items WHERE id = $1::uuid AND user_id = $2::uuid",
                    watch_id, user_id,
                )
                result = await conn.execute(
                    "DELETE FROM public.watchlist_items WHERE id = $1::uuid AND user_id = $2::uuid",
                    watch_id, user_id,
                )
                if result.endswith(" 0"):
                    raise error_response(404, "Watchlist item not found", code="NOT_FOUND")

            # Negative-signal capture (best-effort, after pool released).
            if removed_meta:
                try:
                    from app.features.data_moat import record_demand_signal
                    await record_demand_signal(
                        signal_type="watchlist_remove",
                        category=removed_meta["category"],
                        item_key=removed_meta["item_id"] or removed_meta["title"],
                        user_id=user_id,
                    )
                except Exception as ds_e:
                    logger.debug("[watchlist] demand_signal record failed: %s", ds_e)

            async with pool.acquire() as conn:

                # Return remaining items
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, item_id, name, category,
                           created_at, predicted_value, currency,
                           last_market_price, last_checked_at,
                           price_trend, market_hit_count
                    FROM watchlist
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    """,
                    user_id,
                )
                items = [
                    WatchlistItem(
                        id=str(r["id"]),
                        user_id=r["user_id"],
                        item_id=r["item_id"],
                        name=r["name"],
                        category=r["category"],
                        created_at=r["created_at"],
                        predicted_value=float(r["predicted_value"]) if r["predicted_value"] else None,
                        currency=r["currency"] or "EUR",
                        last_market_price=float(r["last_market_price"]) if r["last_market_price"] else None,
                        last_checked_at=r["last_checked_at"],
                        price_trend=r["price_trend"],
                        market_hit_count=r["market_hit_count"] or 0,
                    )
                    for r in rows
                ]
                return WatchlistResponse(items=items)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[watchlist] DB error removing from watchlist: %s", e)
            raise error_response(500, "Failed to remove from watchlist", code="DB_ERROR")

    # In-memory fallback
    items = _WATCHLIST.get(user_id, [])
    new_items = [it for it in items if it.id != watch_id]
    if len(new_items) == len(items):
        raise error_response(404, "Watchlist item not found", code="NOT_FOUND")
    _WATCHLIST[user_id] = new_items
    return WatchlistResponse(items=new_items)
