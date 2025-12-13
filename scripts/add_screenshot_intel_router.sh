#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create screenshot_intel_router.py
##############################################

if [ -f app/features/screenshot_intel_router.py ]; then
  echo "app/features/screenshot_intel_router.py already exists, skipping creation."
else
  cat > app/features/screenshot_intel_router.py <<'PY'
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/screenshot-intel", tags=["screenshot-intel"])


class ScreenshotIntelRequest(BaseModel):
    screenshot_id: str = Field(..., description="Identifier of the uploaded screenshot")
    source_hint: Optional[str] = Field(
        None, description="ebay | vinted | instagram | reddit | other"
    )


class ScreenshotItemIntel(BaseModel):
    item_name: str
    estimated_value: float
    currency: str = "EUR"
    source_url: Optional[str] = None
    can_add_to_watchlist: bool = True
    listing_platform: Optional[str] = None


class ScreenshotIntelResponse(BaseModel):
    screenshot_id: str
    items: List[ScreenshotItemIntel]


@router.post("/analyze", response_model=ScreenshotIntelResponse)
async def analyze_screenshot(payload: ScreenshotIntelRequest) -> ScreenshotIntelResponse:
    """
    Proof-of-concept screenshot extraction.

    Later this will use multimodal OCR + scraping.
    For now, returns one deterministic item per screenshot.
    """
    platform = payload.source_hint or "ebay"
    item = ScreenshotItemIntel(
        item_name="Demo Grail from screenshot",
        estimated_value=120.0,
        currency="EUR",
        source_url="https://example.com/demo-listing",
        can_add_to_watchlist=True,
        listing_platform=platform,
    )
    return ScreenshotIntelResponse(
        screenshot_id=payload.screenshot_id,
        items=[item],
    )
PY
fi

##############################################
# 2) Ensure app/features/__init__.py exports it
##############################################

python <<'PY'
from pathlib import Path

init_path = Path("app/features/__init__.py")
text = init_path.read_text()
if "screenshot_intel_router" not in text:
    text += "from . import screenshot_intel_router  # noqa: F401\n"
    init_path.write_text(text)
    print("Updated app/features/__init__.py to export screenshot_intel_router")
else:
    print("app/features/__init__.py already exports screenshot_intel_router")
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
cp "$MAIN_FILE" "$MAIN_FILE.bak.screenshot.$(date +%s)"

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

import_line = "from app.features import screenshot_intel_router\n"
include_line = "app.include_router(screenshot_intel_router.router)\n"

if "screenshot_intel_router" not in text:
    text = import_line + text

if "app.include_router(screenshot_intel_router.router)" not in text:
    if not text.endswith("\\n"):
        text += "\\n"
    text += "\\n# Auto-wired screenshot intel router\\n" + include_line

main_path.write_text(text)
print(f"screenshot_intel_router wired into {main_path}")
PY

echo "Done: screenshot intel router added and wired."
