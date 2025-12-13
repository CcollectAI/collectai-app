#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create watchlist_router.py
##############################################

if [ -f app/features/watchlist_router.py ]; then
  echo "app/features/watchlist_router.py already exists, skipping creation."
else
  cat > app/features/watchlist_router.py <<'PY'
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    item_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    predicted_value: Optional[float] = None
    currency: str = "EUR"


class WatchlistCreate(BaseModel):
    item_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    predicted_value: Optional[float] = None
    currency: str = "EUR"


class WatchlistResponse(BaseModel):
    items: List[WatchlistItem]


# In-memory store keyed by user_id
_WATCHLIST: dict[str, list[WatchlistItem]] = {}


def _get_user_id() -> str:
    # Later: derive from auth/session. For now: demo user.
    return "demo-user"


@router.get("/mine", response_model=WatchlistResponse)
async def get_my_watchlist() -> WatchlistResponse:
    user_id = _get_user_id()
    items = _WATCHLIST.get(user_id, [])
    return WatchlistResponse(items=items)


@router.post("/mine", response_model=WatchlistItem)
async def add_to_watchlist(payload: WatchlistCreate) -> WatchlistItem:
    user_id = _get_user_id()
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
async def remove_from_watchlist(watch_id: str) -> WatchlistResponse:
    user_id = _get_user_id()
    items = _WATCHLIST.get(user_id, [])
    new_items = [it for it in items if it.id != watch_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    _WATCHLIST[user_id] = new_items
    return WatchlistResponse(items=new_items)
PY
fi

##############################################
# 2) Ensure app/features/__init__.py exports it
##############################################

python <<'PY'
from pathlib import Path

init_path = Path("app/features/__init__.py")
text = init_path.read_text()
if "watchlist_router" not in text:
    text += "\nfrom . import watchlist_router  # noqa: F401\n"
    init_path.write_text(text)
    print("Updated app/features/__init__.py to export watchlist_router")
else:
    print("app/features/__init__.py already exports watchlist_router")
PY

##############################################
# 3) Wire router into main.py or app/main.py
##############################################

if [ -f "main.py" ]; then
  MAIN_FILE="main.py"
elif [ -f "app/main.py" ]; then
  MAIN_FILE="app/main.py"
else
  echo "ERROR: Could not find main.py or app/main.py" >&2
  exit 1
fi

echo "Using main file: $MAIN_FILE"
cp "$MAIN_FILE" "$MAIN_FILE.bak.watchlist.$(date +%s)"

python <<'PY'
from pathlib import Path

candidates = ["main.py", "app/main.py"]
main_path = None
for c in candidates:
    p = Path(c)
    if p.exists():
        main_path = p
        break

if main_path is None:
    raise SystemExit("No main file found.")

text = main_path.read_text()

import_line = "from app.features import watchlist_router\n"
include_line = "app.include_router(watchlist_router.router)\n"

if "watchlist_router" not in text:
    text = import_line + text

if "app.include_router(watchlist_router.router)" not in text:
    if not text.endswith("\\n"):
        text += "\\n"
    text += "\\n# Auto-wired watchlist router\\n" + include_line

main_path.write_text(text)
print(f"watchlist_router wired into {main_path}")
PY

echo "Done: watchlist router added and wired."
