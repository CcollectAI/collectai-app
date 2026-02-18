"""
Demo items router.

In-memory item store used by the QuickScan → Add flow.
Will be replaced by Supabase-backed persistence later.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["items"])


# ---- Models ----

class ItemCreateRequest(BaseModel):
    name: str
    category: Optional[str] = None
    collection_name: Optional[str] = None
    estimated_value: Optional[float] = None
    notes: Optional[str] = None


class ItemResponse(ItemCreateRequest):
    id: str


# ---- In-memory store ----

_DEMO_ITEMS: list[ItemResponse] = []


def get_demo_items() -> list[ItemResponse]:
    """Accessor for the in-memory demo items list (used by portfolio router)."""
    return _DEMO_ITEMS


# ---- Endpoints ----

@router.post("/items", response_model=ItemResponse)
async def create_item(payload: ItemCreateRequest):
    """
    Demo create-item endpoint.
    Stores items in memory so the Items tab can show QuickScan results.
    Later we can swap this to Supabase without changing the frontend.
    """
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
async def list_items():
    """List all demo items stored in memory."""
    return _DEMO_ITEMS
