from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.error_codes import ErrorCode
from app.rate_limit import per_user_rate_limit

from app.db import db_configured, get_conn

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

router = APIRouter(prefix="/alerts", tags=["Alerts"])

_alert_write_limit = per_user_rate_limit(20, window_seconds=60, scope="alert_write")


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_triggered_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class PriceAlertCreate(BaseModel):
    item_id: Optional[str] = None
    category: Optional[str] = None
    trigger_type: Literal["below_threshold", "category_trend", "high_prediction"] = "below_threshold"
    threshold_value: Optional[float] = Field(None, gt=0, le=1_000_000)
    direction: Optional[Literal["up", "down"]] = None
    metadata: dict = Field(default_factory=dict)


class PriceAlertListResponse(BaseModel):
    alerts: List[PriceAlert]


# In-memory store for DB_DISABLED mode
_IN_MEMORY_ALERTS: dict[str, PriceAlert] = {}


@router.get("/mine", response_model=PriceAlertListResponse)
async def list_my_alerts(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """
    List all alerts for the current user.

    - If DB is disabled: use in-memory store.
    - If DB is enabled: read from user_price_alerts table.
    """
    limit, offset = pagination

    if not db_configured():
        alerts = [a for a in _IN_MEMORY_ALERTS.values() if a.user_id == user_id]
        return PriceAlertListResponse(alerts=alerts[offset:offset + limit])

    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, item_id, category, trigger_type,
                   threshold_value, direction, active, created_at,
                   last_triggered_at, metadata
            FROM public.user_price_alerts
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
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
    _rl=Depends(_alert_write_limit),
):
    """
    Create or update a price alert for the current user.

    This is the user-friendly wrapper around your alert engine:
    - 'Alert me when this item drops below €X'
    - 'Alert me when category prices start trending'
    - 'Alert me when predicted value is unusually high'
    """
    if alert_id is not None and not _UUID_RE.match(alert_id):
        raise error_response(400, "Invalid alert_id format", code=ErrorCode.INVALID_UUID)
    if payload.item_id is not None and not _UUID_RE.match(payload.item_id):
        raise error_response(400, "Invalid item_id format", code=ErrorCode.INVALID_UUID)

    is_create = alert_id is None
    if alert_id is None:
        alert_id = str(uuid4())

    # Free plan is capped at N price-alert creations per rolling 7 days; Pro /
    # Premium are unlimited (max_alerts_per_week=None). Enforced only for real
    # creates on the DB path — the in-memory dev fallback has no durable count.
    if is_create and db_configured():
        from app.subscription import get_user_plan
        from app.routes.billing_router import PLAN_LIMITS

        plan = await get_user_plan(user_id)
        weekly_cap = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).get("max_alerts_per_week")
        if weekly_cap is not None:
            async with get_conn() as conn:
                recent = await conn.fetchval(
                    """
                    SELECT count(*) FROM public.user_price_alerts
                    WHERE user_id = $1 AND created_at >= now() - interval '7 days'
                    """,
                    user_id,
                )
            if (recent or 0) >= weekly_cap:
                raise error_response(
                    403,
                    f"The free plan includes {weekly_cap} price alert per week. "
                    "Upgrade to Pro for unlimited alerts.",
                    code="PLAN_LIMIT_ALERTS",
                )

    now = datetime.now(timezone.utc)
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

    if not db_configured():
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

    # Record demand signal with geo enrichment (best-effort)
    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="price_alert_set",
            category=payload.category,
            item_key=payload.item_id,
            user_id=user_id,
            region=region,
            country_code=country,
        )
    except Exception as e:
        logger.debug("Demand signal recording failed (best-effort): %s", e)

    return alert


@router.delete("/mine/{alert_id}")
async def delete_alert(alert_id: str, user_id: str = Depends(get_current_user_id), _rl=Depends(_alert_write_limit)):
    """
    Delete/disable a user's alert (soft delete by setting active=false).
    """
    if not _UUID_RE.match(alert_id):
        raise error_response(400, "Invalid alert_id format", code=ErrorCode.INVALID_UUID)

    if not db_configured():
        existing = _IN_MEMORY_ALERTS.get(alert_id)
        if existing and existing.user_id == user_id:
            del _IN_MEMORY_ALERTS[alert_id]
            return {"ok": True}
        raise error_response(404, "Alert not found", code="VALIDATION_ERROR")

    removed_meta = None
    async with get_conn() as conn:
        removed_meta = await conn.fetchrow(
            "SELECT category, item_id FROM public.user_price_alerts WHERE id = $1 AND user_id = $2",
            alert_id, user_id,
        )
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
        if result.endswith(" 0"):
            raise error_response(404, "Alert not found", code="VALIDATION_ERROR")

    # Negative signal — alert removal is an annoyance/satisfaction signal
    # that feeds the (deferred) alert_quality_worker.
    if removed_meta:
        try:
            from app.features.data_moat import record_demand_signal
            await record_demand_signal(
                signal_type="price_alert_removed",
                category=removed_meta["category"],
                item_key=removed_meta["item_id"],
                user_id=user_id,
            )
        except Exception:
            pass
    return {"ok": True}


# ---------------------------------------------------------------------------
# Trigger history — records of when alerts actually fired
# ---------------------------------------------------------------------------


@router.get("/trigger-history")
async def get_trigger_history(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Return alert trigger events for the current user, paginated."""
    limit, offset = pagination

    if not db_configured():
        return {"triggers": [], "unread_count": 0}

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT id, alert_id, item_id, trigger_type, trigger_value,
                       message, read, created_at
                FROM public.alert_trigger_history
                WHERE user_id = $1::text::uuid
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )

            unread = await conn.fetchval(
                """
                SELECT count(*)
                FROM public.alert_trigger_history
                WHERE user_id = $1::text::uuid AND read = false
                """,
                user_id,
            )
    except asyncpg.PostgresError:
        logger.warning("trigger-history query failed for user=%s", user_id, exc_info=True)
        return {"triggers": [], "unread_count": 0}

    return {
        "triggers": [
            {
                "id": str(r["id"]),
                "alert_id": str(r["alert_id"]) if r["alert_id"] else None,
                "item_id": r["item_id"],
                "trigger_type": r["trigger_type"],
                "trigger_value": r["trigger_value"],  # asyncpg auto-deserialises JSONB
                "message": r["message"],
                "read": r["read"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "unread_count": unread or 0,
    }


@router.post("/trigger-history/{trigger_id}/read")
async def mark_trigger_read(trigger_id: str, user_id: str = Depends(get_current_user_id)):
    """Mark a single trigger-history entry as read."""
    if not _UUID_RE.match(trigger_id):
        raise error_response(400, "Invalid trigger_id format", code=ErrorCode.INVALID_UUID)

    if not db_configured():
        return {"ok": True}

    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                UPDATE public.alert_trigger_history
                SET read = true
                WHERE id = $1::text::uuid AND user_id = $2::text::uuid
                """,
                trigger_id,
                user_id,
            )
    except asyncpg.PostgresError:
        logger.warning(
            "mark_trigger_read failed trigger=%s user=%s", trigger_id, user_id, exc_info=True
        )
    return {"ok": True}
