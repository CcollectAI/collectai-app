#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

ROUTER_FILE="app/features/items_export_router.py"

if [ ! -f "$ROUTER_FILE" ]; then
  echo "Creating $ROUTER_FILE"
  cat <<'PY' > "$ROUTER_FILE"
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
PY
else
  echo "$ROUTER_FILE already exists, skipping creation."
fi

echo "Backing up main.py"
cp main.py "main.py.bak.items_export.$(date +%s)"

# Wire import + include at the end of main.py if not already present
if ! grep -q "from app.features import items_export_router" main.py; then
  printf '\nfrom app.features import items_export_router\n' >> main.py
  echo "Added import for items_export_router to main.py"
fi

if ! grep -q "app.include_router(items_export_router.router)" main.py; then
  printf '\napp.include_router(items_export_router.router)\n' >> main.py
  echo "Added app.include_router for items_export_router to main.py"
fi

echo "Done: items_export_router created and wired."
