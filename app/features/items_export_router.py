from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/items-export", tags=["items-export"])


class ItemsExportResponse(BaseModel):
  download_url: Optional[str] = None
  csv_inline: str


@router.get("/overview", response_model=ItemsExportResponse)
async def export_items_overview() -> ItemsExportResponse:
  # Stub CSV – later this will come from Supabase or your DB.
  csv = (
      "id,name,category,value,currency\n"
      "p1,Demo Charizard,pokemon,124,EUR\n"
      "p2,Grail Funko Pop,funko,45,EUR\n"
      "p3,Wave 1 RX-78 (Launch),gunpla,220,EUR\n"
  )
  return ItemsExportResponse(
      download_url=None,
      csv_inline=csv,
  )
