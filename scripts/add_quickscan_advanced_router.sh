#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create quickscan_advanced_router.py
##############################################

if [ -f app/features/quickscan_advanced_router.py ]; then
  echo "app/features/quickscan_advanced_router.py already exists, skipping creation."
else
  cat > app/features/quickscan_advanced_router.py <<'PY'
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/quickscan-advanced", tags=["quickscan-advanced"])


class QuickScanAttributes(BaseModel):
    category: str
    edition_guess: str | None = None
    condition_guess: str | None = None
    rarity_score: float | None = Field(
        None, description="0-1 rarity estimate based on visual cues"
    )


class QuickScanPrediction(BaseModel):
    name: str
    estimated_low: float
    estimated_mid: float
    estimated_high: float
    currency: str = "EUR"
    confidence: float = Field(..., description="0-1 model confidence")


class QuickScanResult(BaseModel):
    item_id: str | None = None
    attributes: QuickScanAttributes
    prediction: QuickScanPrediction


class BatchQuickScanRequest(BaseModel):
    image_ids: List[str] = Field(
        ..., description="Identifiers of uploaded images (S3 keys, etc.)"
    )


class BatchQuickScanResponse(BaseModel):
    results: List[QuickScanResult]


@router.post("/single", response_model=QuickScanResult)
async def quickscan_single_demo() -> QuickScanResult:
    """
    Enriched QuickScan: edition, condition, rarity, q10/q50/q90 band.

    Later this will call your real multimodal model; for now,
    it's a deterministic demo object so the Add flow can be wired.
    """
    attrs = QuickScanAttributes(
        category="mtg",
        edition_guess="Unlimited",
        condition_guess="Near Mint",
        rarity_score=0.82,
    )
    pred = QuickScanPrediction(
        name="Demo Black Lotus",
        estimated_low=18000.0,
        estimated_mid=22000.0,
        estimated_high=26000.0,
        currency="EUR",
        confidence=0.91,
    )
    return QuickScanResult(
        item_id=None,
        attributes=attrs,
        prediction=pred,
    )


@router.post("/batch", response_model=BatchQuickScanResponse)
async def quickscan_batch_demo(payload: BatchQuickScanRequest) -> BatchQuickScanResponse:
    """
    Multi-item batch scanning (Advanced D).
    For now returns 1 demo item per image_id.
    """
    results: list[QuickScanResult] = []
    for image_id in payload.image_ids:
        attrs = QuickScanAttributes(
            category="funko",
            edition_guess="Convention Exclusive",
            condition_guess="Boxed",
            rarity_score=0.7,
        )
        pred = QuickScanPrediction(
            name=f"Demo Funko from {image_id}",
            estimated_low=35.0,
            estimated_mid=45.0,
            estimated_high=60.0,
            currency="EUR",
            confidence=0.8,
        )
        results.append(
            QuickScanResult(
                item_id=None,
                attributes=attrs,
                prediction=pred,
            )
        )
    return BatchQuickScanResponse(results=results)
PY
fi

##############################################
# 2) Ensure app/features/__init__.py exports it
##############################################

python <<'PY'
from pathlib import Path

init_path = Path("app/features/__init__.py")
text = init_path.read_text()
if "quickscan_advanced_router" not in text:
    text += "from . import quickscan_advanced_router  # noqa: F401\n"
    init_path.write_text(text)
    print("Updated app/features/__init__.py to export quickscan_advanced_router")
else:
    print("app/features/__init__.py already exports quickscan_advanced_router")
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
cp "$MAIN_FILE" "$MAIN_FILE.bak.quickscan.$(date +%s)"

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

import_line = "from app.features import quickscan_advanced_router\n"
include_line = "app.include_router(quickscan_advanced_router.router)\n"

if "quickscan_advanced_router" not in text:
    text = import_line + text

if "app.include_router(quickscan_advanced_router.router)" not in text:
    if not text.endswith("\\n"):
        text += "\\n"
    text += "\\n# Auto-wired quickscan advanced router\\n" + include_line

main_path.write_text(text)
print(f"quickscan_advanced_router wired into {main_path}")
PY

echo "Done: quickscan advanced router added and wired."
