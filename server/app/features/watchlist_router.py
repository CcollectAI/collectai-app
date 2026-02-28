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

import logging

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
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


@router.get("/mine", response_model=WatchlistResponse)
async def get_my_watchlist(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> WatchlistResponse:
    limit, offset = pagination
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, item_id, name, category,
                           created_at, predicted_value, currency,
                           last_market_price, last_checked_at,
                           price_trend, market_hit_count
                    FROM watchlist
                    WHERE user_id = $1
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


@router.post("/mine", response_model=WatchlistItem)
async def add_to_watchlist(payload: WatchlistCreate, user_id: str = Depends(get_current_user_id)) -> WatchlistItem:
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
                    INSERT INTO watchlist (id, user_id, item_id, name, category,
                                           created_at, predicted_value, currency)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    item.id, user_id, payload.item_id, payload.name,
                    payload.category, item.created_at,
                    payload.predicted_value, payload.currency,
                )
                logger.info("[watchlist] Added item: id=%s, user=%s", item.id, user_id)

                # Record demand signal (best-effort)
                try:
                    from app.features.data_moat import record_demand_signal
                    await record_demand_signal(
                        signal_type="watchlist_add",
                        category=payload.category,
                        item_key=payload.name or payload.item_id,
                        user_id=user_id,
                    )
                except Exception:
                    pass

                return item
        except Exception as e:
            logger.error("[watchlist] DB error adding to watchlist: %s", e)
            raise error_response(500, "Failed to add to watchlist", code="DB_ERROR")

    # In-memory fallback
    _WATCHLIST.setdefault(user_id, []).append(item)
    return item


@router.delete("/mine/{watch_id}", response_model=WatchlistResponse)
async def remove_from_watchlist(watch_id: str, user_id: str = Depends(get_current_user_id)) -> WatchlistResponse:
    pool = get_db_pool()

    if pool is not None:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM watchlist WHERE id = $1 AND user_id = $2",
                    watch_id, user_id,
                )
                if result.endswith(" 0"):
                    raise error_response(404, "Watchlist item not found", code="NOT_FOUND")

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
