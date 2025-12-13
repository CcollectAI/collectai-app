#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create insights_router.py
##############################################

if [ -f app/features/insights_router.py ]; then
  echo "app/features/insights_router.py already exists, skipping creation."
else
  cat > app/features/insights_router.py <<'PY'
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/insights", tags=["insights"])


class CategoryExposure(BaseModel):
    category: str
    share_pct: float
    risk_level: str = Field(..., description="low | medium | high")


class RareSetAlert(BaseModel):
    category: str
    item_name: str
    note: str


class TrendingItem(BaseModel):
    category: str
    item_name: str
    change_pct: float


class PersonalizedInsightsResponse(BaseModel):
    overexposed_categories: List[CategoryExposure]
    diversification_suggestions: List[str]
    rare_set_alerts: List[RareSetAlert]
    trending_items: List[TrendingItem]


class HomeWidgetResponse(BaseModel):
    collection_value: float
    today_change: float
    biggest_mover_name: str
    biggest_mover_change: float
    currency: str = "EUR"
    quickscan_shortcut: str = Field(
        "/quickscan-advanced/single", description="Relative path for one-tap scan"
    )


@router.get("/personalized", response_model=PersonalizedInsightsResponse)
async def get_personalized_insights() -> PersonalizedInsightsResponse:
    overexposed = [
        CategoryExposure(category="gunpla", share_pct=0.45, risk_level="medium"),
        CategoryExposure(category="mtg", share_pct=0.35, risk_level="high"),
    ]
    diversification = [
        "Consider adding more Warhammer minis to reduce TCG concentration.",
        "Your Gunpla exposure is high vs. Funko and Designer Toys.",
    ]
    rare_alerts = [
        RareSetAlert(
            category="gunpla",
            item_name="Wave 1 RX-78 (Launch)",
            note="Likely to retire in the next cycle.",
        )
    ]
    trending = [
        TrendingItem(
            category="designer-toys",
            item_name="Labubu-style collab drop",
            change_pct=0.32,
        )
    ]
    return PersonalizedInsightsResponse(
        overexposed_categories=overexposed,
        diversification_suggestions=diversification,
        rare_set_alerts=rare_alerts,
        trending_items=trending,
    )


@router.get("/home-widget", response_model=HomeWidgetResponse)
async def get_home_widget() -> HomeWidgetResponse:
    """
    'What's it worth today?' home widget snapshot.
    """
    return HomeWidgetResponse(
        collection_value=12450.0,
        today_change=+145.0,
        biggest_mover_name="Demo Charizard",
        biggest_mover_change=+12.5,
        currency="EUR",
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
if "insights_router" not in text:
    text += "from . import insights_router  # noqa: F401\n"
    init_path.write_text(text)
    print("Updated app/features/__init__.py to export insights_router")
else:
    print("app/features/__init__.py already exports insights_router")
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
cp "$MAIN_FILE" "$MAIN_FILE.bak.insights.$(date +%s)"

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

import_line = "from app.features import insights_router\n"
include_line = "app.include_router(insights_router.router)\n"

if "insights_router" not in text:
    text = import_line + text

if "app.include_router(insights_router.router)" not in text:
    if not text.endswith("\\n"):
        text += "\\n"
    text += "\\n# Auto-wired insights router\\n" + include_line

main_path.write_text(text)
print(f"insights_router wired into {main_path}")
PY

echo "Done: insights router added and wired."
