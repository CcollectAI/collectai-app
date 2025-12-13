#!/usr/bin/env bash
set -euo pipefail

# Go to repo root (this script lives in ./scripts/)
cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create alerts_feature_router.py (if missing)
##############################################

if [ -f app/features/alerts_feature_router.py ]; then
  echo "app/features/alerts_feature_router.py already exists, skipping creation."
else
  cat > app/features/alerts_feature_router.py <<'PY'
from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"

router = APIRouter(prefix="/alerts", tags=["alerts"])


class PriceAlert(BaseModel):
    id: str = Field(..., description="Alert ID")
    user_id: str = Field(..., description="Owner user ID")
    item_id: Optional[str] = Field(
        None, description="Specific item to watch; null for category/global"
    )
    category: Optional[str] = Field(
        None, description="Optional category (e.g. 'mtg', 'funko')"
    )
    trigger_type: str = Field(
        ...,
        description="below_threshold | category_trend | high_prediction",
    )
    threshold_value: Optional[float] = Field(
        None, description="For below_threshold triggers"
    )
    direction: Optional[str] = Field(
        None, description="up | down for trend-style triggers"
    )
    active: bool = Field(True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class PriceAlertCreate(BaseModel):
    item_id: Optional[str] = None
    category: Optional[str] = None
    trigger_type: str
    threshold_value: Optional[float] = None
    direction: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class PriceAlertListResponse(BaseModel):
    alerts: List[PriceAlert]


def get_current_user_id() -> str:
    # TODO: replace with real auth
    return "demo-user"


# In-memory store for DB_DISABLED mode
_IN_MEMORY_ALERTS: dict[str, PriceAlert] = {}


@router.get("/mine", response_model=PriceAlertListResponse)
async def list_my_alerts(user_id: str = Depends(get_current_user_id)):
    """
    List all alerts for the current user.

    - If DB is disabled: use in-memory store.
    - If DB is enabled: TODO – read from alerts table.
    """
    if not DB_ENABLED:
        alerts = [a for a in _IN_MEMORY_ALERTS.values() if a.user_id == user_id]
        return PriceAlertListResponse(alerts=alerts)

    # TODO: implement DB query when DB wiring resumes
    return PriceAlertListResponse(alerts=[])


@router.post("/mine", response_model=PriceAlert)
async def create_or_update_alert(
    payload: PriceAlertCreate,
    alert_id: Optional[str] = Query(
        default=None, description="If provided, updates an existing alert"
    ),
    user_id: str = Depends(get_current_user_id),
):
    """
    Create or update a price alert for the current user.

    This is the user-friendly wrapper around your alert engine:
    - 'Alert me when this item drops below €X'
    - 'Alert me when category prices start trending'
    - 'Alert me when predicted value is unusually high'
    """
    from uuid import uuid4

    if alert_id is None:
        alert_id = str(uuid4())

    alert = PriceAlert(
        id=alert_id,
        user_id=user_id,
        item_id=payload.item_id,
        category=payload.category,
        trigger_type=payload.trigger_type,
        threshold_value=payload.threshold_value,
        direction=payload.direction,
        active=True,
        metadata=payload.metadata or {},
    )

    if not DB_ENABLED:
        _IN_MEMORY_ALERTS[alert_id] = alert
        return alert

    # TODO: upsert to alerts table (DB_ENABLED mode)
    return alert


@router.delete("/mine/{alert_id}")
async def delete_alert(alert_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Delete/disable a user's alert.
    """
    if not DB_ENABLED:
        existing = _IN_MEMORY_ALERTS.get(alert_id)
        if existing and existing.user_id == user_id:
            del _IN_MEMORY_ALERTS[alert_id]
            return {"ok": True}
        raise HTTPException(status_code=404, detail="Alert not found")

    # TODO: mark alert inactive in DB when wired
    return {"ok": True, "note": "DB delete not yet wired"}
PY
fi

##############################################
# 2) Wire the router into app/main.py (safe)
##############################################

if [ ! -f app/main.py ]; then
  echo "ERROR: app/main.py not found" >&2
  exit 1
fi

# Backup main.py with timestamp
cp app/main.py "app/main.py.bak.$(date +%s)"

python <<'PY'
from pathlib import Path

main_path = Path("app/main.py")
text = main_path.read_text()

import_line = "from app.features import alerts_feature_router\n"
include_line = "app.include_router(alerts_feature_router.router)\n"

# Add import if not already present
if "alerts_feature_router" not in text:
    text = import_line + text

# Add include_router if not already present
if "app.include_router(alerts_feature_router.router)" not in text:
    # Append near the end; simple but safe
    if not text.endswith("\n"):
        text += "\n"
    text += "\n# Auto-wired alerts router\n" + include_line

main_path.write_text(text)
print("alerts_feature_router wired into app/main.py")
PY

echo "Done: alerts router added and wired."
