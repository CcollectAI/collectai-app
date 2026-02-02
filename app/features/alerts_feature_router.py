from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import db_configured, get_conn

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
    - If DB is enabled: read from user_price_alerts table.
    """
    if not DB_ENABLED:
        alerts = [a for a in _IN_MEMORY_ALERTS.values() if a.user_id == user_id]
        return PriceAlertListResponse(alerts=alerts)

    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, item_id, category, trigger_type,
                   threshold_value, direction, active, created_at,
                   last_triggered_at, metadata
            FROM public.user_price_alerts
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )

    alerts = [
        PriceAlert(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            item_id=str(row["item_id"]) if row["item_id"] else None,
            category=row["category"],
            trigger_type=row["trigger_type"],
            threshold_value=float(row["threshold_value"]) if row["threshold_value"] else None,
            direction=row["direction"],
            active=row["active"],
            created_at=row["created_at"],
            last_triggered_at=row["last_triggered_at"],
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )
        for row in rows
    ]
    return PriceAlertListResponse(alerts=alerts)


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

    now = datetime.utcnow()
    alert = PriceAlert(
        id=alert_id,
        user_id=user_id,
        item_id=payload.item_id,
        category=payload.category,
        trigger_type=payload.trigger_type,
        threshold_value=payload.threshold_value,
        direction=payload.direction,
        active=True,
        created_at=now,
        metadata=payload.metadata or {},
    )

    if not DB_ENABLED:
        _IN_MEMORY_ALERTS[alert_id] = alert
        return alert

    async with get_conn() as conn:
        # Upsert: insert or update on conflict
        await conn.execute(
            """
            INSERT INTO public.user_price_alerts (
                id, user_id, item_id, category, trigger_type,
                threshold_value, direction, active, created_at, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                category = EXCLUDED.category,
                trigger_type = EXCLUDED.trigger_type,
                threshold_value = EXCLUDED.threshold_value,
                direction = EXCLUDED.direction,
                active = EXCLUDED.active,
                metadata = EXCLUDED.metadata
            """,
            alert_id,
            user_id,
            payload.item_id,
            payload.category,
            payload.trigger_type,
            payload.threshold_value,
            payload.direction,
            True,
            now,
            json.dumps(payload.metadata or {}),
        )
    return alert


@router.delete("/mine/{alert_id}")
async def delete_alert(alert_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Delete/disable a user's alert (soft delete by setting active=false).
    """
    if not DB_ENABLED:
        existing = _IN_MEMORY_ALERTS.get(alert_id)
        if existing and existing.user_id == user_id:
            del _IN_MEMORY_ALERTS[alert_id]
            return {"ok": True}
        raise HTTPException(status_code=404, detail="Alert not found")

    async with get_conn() as conn:
        result = await conn.execute(
            """
            UPDATE public.user_price_alerts
            SET active = false
            WHERE id = $1 AND user_id = $2
            """,
            alert_id,
            user_id,
        )
        # result is like "UPDATE 1" or "UPDATE 0"
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}
