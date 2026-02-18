from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.features.pagination import pagination_params

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    item_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    predicted_value: Optional[float] = None
    currency: str = "EUR"


class WatchlistCreate(BaseModel):
    item_id: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=64)
    predicted_value: Optional[float] = None
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")


class WatchlistResponse(BaseModel):
    items: List[WatchlistItem]


# In-memory store keyed by user_id
_WATCHLIST: dict[str, list[WatchlistItem]] = {}


@router.get("/mine", response_model=WatchlistResponse)
async def get_my_watchlist(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> WatchlistResponse:
    limit, offset = pagination
    items = _WATCHLIST.get(user_id, [])
    return WatchlistResponse(items=items[offset:offset + limit])


@router.post("/mine", response_model=WatchlistItem)
async def add_to_watchlist(payload: WatchlistCreate, user_id: str = Depends(get_current_user_id)) -> WatchlistItem:
    item = WatchlistItem(
        user_id=user_id,
        item_id=payload.item_id,
        name=payload.name,
        category=payload.category,
        predicted_value=payload.predicted_value,
        currency=payload.currency,
    )
    _WATCHLIST.setdefault(user_id, []).append(item)
    return item


@router.delete("/mine/{watch_id}", response_model=WatchlistResponse)
async def remove_from_watchlist(watch_id: str, user_id: str = Depends(get_current_user_id)) -> WatchlistResponse:
    items = _WATCHLIST.get(user_id, [])
    new_items = [it for it in items if it.id != watch_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    _WATCHLIST[user_id] = new_items
    return WatchlistResponse(items=new_items)
