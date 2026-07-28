"""
Purchase Router — Smart Deal Agent REST endpoints.

CRUD for purchase mandates + deal actions (click, confirm, decline) + stats.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.rate_limit import per_user_rate_limit
from app.errors import error_response
from app.db import db_configured, get_conn
from app.features.pagination import pagination_params
from app.subscription import get_user_mandate_limit, require_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/purchase", tags=["Purchase"])

# Per-user: 10 deal confirm requests per minute
_deal_confirm_limit = per_user_rate_limit(10, window_seconds=60, scope="deal_confirm")

# Per-user: 10 mandate write (create/update/delete) requests per minute
_mandate_write_limit = per_user_rate_limit(10, window_seconds=60, scope="mandate_write")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class MandateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    search_query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    condition_filter: List[str] = Field(default_factory=list)
    min_trust_score: float = Field(default=0.60, ge=0.0, le=1.0)
    max_price: float = Field(..., gt=0, le=1_000_000)
    max_total_budget: Optional[float] = Field(None, gt=0, le=10_000_000)
    cooldown_hours: int = Field(default=24, ge=1, le=720)
    allowed_sources: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    region: Optional[str] = None
    expires_at: Optional[str] = None


class MandateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[Literal["active", "paused"]] = None
    category: Optional[str] = None
    condition_filter: Optional[List[str]] = None
    min_trust_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_price: Optional[float] = Field(None, gt=0, le=1_000_000)
    max_total_budget: Optional[float] = Field(None, gt=0, le=10_000_000)
    cooldown_hours: Optional[int] = Field(None, ge=1, le=720)
    allowed_sources: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    region: Optional[str] = None
    expires_at: Optional[str] = None


class MandateResponse(BaseModel):
    id: str
    name: str
    status: str
    search_query: str
    category: Optional[str] = None
    condition_filter: List[str] = Field(default_factory=list)
    min_trust_score: float = 0.60
    max_price: float
    max_total_budget: Optional[float] = None
    spent_total: float = 0.0
    cooldown_hours: int = 24
    allowed_sources: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    region: Optional[str] = None
    expires_at: Optional[str] = None
    last_scan_at: Optional[str] = None
    last_deal_at: Optional[str] = None
    deals_found: int = 0
    deals_purchased: int = 0
    created_at: str
    updated_at: str


class MandateListResponse(BaseModel):
    mandates: List[MandateResponse]
    total: int


class DealResponse(BaseModel):
    id: str
    mandate_id: str
    status: str
    listing_source: str
    listing_url: str
    affiliate_url: Optional[str] = None
    listing_title: str
    listing_price: float
    listing_currency: str = "EUR"
    listing_condition: Optional[str] = None
    listing_image_url: Optional[str] = None
    listing_seller: Optional[str] = None
    listing_ended: bool = False
    provenance_score: Optional[float] = None
    deal_score: Optional[float] = None
    price_vs_q50_pct: Optional[float] = None
    predicted_q50: Optional[float] = None
    predicted_q10: Optional[float] = None
    predicted_q90: Optional[float] = None
    policy_passed: bool = True
    policy_reasons: list = Field(default_factory=list)
    affiliate_source: Optional[str] = None
    affiliate_click: bool = False
    # D3: deliberately left unpopulated (always None) pre-launch. Real
    # commission comes from per-network conversion reconciliation, which
    # docs/AFFILIATE_SWITCH_ON.md explicitly DEFERS until volume justifies it
    # ("reconcile manually from each network's dashboard"). Kept as a NULL
    # placeholder rather than fabricating a number; the FE renders null as "—".
    estimated_commission: Optional[float] = None
    confirmed_price: Optional[float] = None
    added_item_id: Optional[str] = None
    discovered_at: str
    notified_at: Optional[str] = None
    clicked_at: Optional[str] = None
    purchased_at: Optional[str] = None
    created_at: str


class DealListResponse(BaseModel):
    deals: List[DealResponse]
    total: int


class DealConfirmBody(BaseModel):
    confirmed_price: Optional[float] = Field(None, ge=0)


# Valid status transitions for deal actions
_CLICKABLE_STATUSES = {"discovered", "notified"}
_CONFIRMABLE_STATUSES = {"discovered", "notified", "clicked"}
_DECLINABLE_STATUSES = {"discovered", "notified", "clicked"}

# Allowed columns for mandate PATCH (whitelist to prevent SQL injection)
_UPDATABLE_MANDATE_COLUMNS = frozenset({
    "name", "status", "category", "condition_filter", "min_trust_score",
    "max_price", "max_total_budget", "cooldown_hours", "allowed_sources",
    "exclude_keywords", "region", "expires_at",
})

# Allowed deal status values for filtering
_VALID_DEAL_STATUSES = frozenset({
    "discovered", "notified", "clicked", "purchased", "declined", "expired",
})

# Explicit column lists for SELECT (avoid SELECT *) — keep in sync with migrations
_MANDATE_COLUMNS = (
    "id, user_id, name, status, search_query, category, condition_filter, "
    "min_trust_score, max_price, max_total_budget, spent_total, cooldown_hours, "
    "allowed_sources, exclude_keywords, region, expires_at, last_scan_at, "
    "last_deal_at, deals_found, deals_purchased, created_at, updated_at"
)
_DEAL_COLUMNS = (
    "id, mandate_id, user_id, status, listing_source, listing_url, affiliate_url, "
    "listing_title, listing_price, listing_currency, listing_condition, "
    "listing_image_url, listing_seller, listing_ended, provenance_score, deal_score, "
    "price_vs_q50_pct, predicted_q50, predicted_q10, predicted_q90, policy_passed, "
    "policy_reasons, affiliate_source, affiliate_click, estimated_commission, "
    "confirmed_price, added_item_id, discovered_at, notified_at, clicked_at, "
    "purchased_at, created_at"
)


class StatsResponse(BaseModel):
    active_mandates: int = 0
    total_deals_found: int = 0
    total_deals_clicked: int = 0
    total_deals_purchased: int = 0
    total_saved_vs_q50: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(dt) -> Optional[str]:
    """Format a datetime/timestamp as ISO string or None."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _row_to_mandate(row) -> dict:
    return MandateResponse(
        id=str(row["id"]),
        name=row["name"],
        status=row["status"],
        search_query=row["search_query"],
        category=row.get("category"),
        condition_filter=list(row.get("condition_filter") or []),
        min_trust_score=float(row.get("min_trust_score") or 0.60),
        max_price=float(row["max_price"]),
        max_total_budget=float(row["max_total_budget"]) if row.get("max_total_budget") else None,
        spent_total=float(row.get("spent_total") or 0),
        cooldown_hours=int(row.get("cooldown_hours") or 24),
        allowed_sources=list(row.get("allowed_sources") or []),
        exclude_keywords=list(row.get("exclude_keywords") or []),
        region=row.get("region"),
        expires_at=_ts(row.get("expires_at")),
        last_scan_at=_ts(row.get("last_scan_at")),
        last_deal_at=_ts(row.get("last_deal_at")),
        deals_found=int(row.get("deals_found") or 0),
        deals_purchased=int(row.get("deals_purchased") or 0),
        created_at=_ts(row["created_at"]) or "",
        updated_at=_ts(row["updated_at"]) or "",
    ).model_dump()


def _row_to_deal(row) -> dict:
    reasons = row.get("policy_reasons")
    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons)
        except (json.JSONDecodeError, TypeError):
            reasons = []
    elif reasons is None:
        reasons = []

    return DealResponse(
        id=str(row["id"]),
        mandate_id=str(row["mandate_id"]),
        status=row["status"],
        listing_source=row["listing_source"],
        listing_url=row["listing_url"],
        affiliate_url=row.get("affiliate_url"),
        listing_title=row["listing_title"],
        listing_price=float(row["listing_price"]),
        listing_currency=row.get("listing_currency", "EUR"),
        listing_condition=row.get("listing_condition"),
        listing_image_url=row.get("listing_image_url"),
        listing_seller=row.get("listing_seller"),
        listing_ended=bool(row.get("listing_ended", False)),
        provenance_score=float(row["provenance_score"]) if row.get("provenance_score") is not None else None,
        deal_score=float(row["deal_score"]) if row.get("deal_score") is not None else None,
        price_vs_q50_pct=float(row["price_vs_q50_pct"]) if row.get("price_vs_q50_pct") is not None else None,
        predicted_q50=float(row["predicted_q50"]) if row.get("predicted_q50") is not None else None,
        predicted_q10=float(row["predicted_q10"]) if row.get("predicted_q10") is not None else None,
        predicted_q90=float(row["predicted_q90"]) if row.get("predicted_q90") is not None else None,
        policy_passed=bool(row.get("policy_passed", True)),
        policy_reasons=reasons,
        affiliate_source=row.get("affiliate_source"),
        affiliate_click=bool(row.get("affiliate_click", False)),
        estimated_commission=float(row["estimated_commission"]) if row.get("estimated_commission") is not None else None,
        confirmed_price=float(row["confirmed_price"]) if row.get("confirmed_price") is not None else None,
        added_item_id=str(row["added_item_id"]) if row.get("added_item_id") else None,
        discovered_at=_ts(row["discovered_at"]) or "",
        notified_at=_ts(row.get("notified_at")),
        clicked_at=_ts(row.get("clicked_at")),
        purchased_at=_ts(row.get("purchased_at")),
        created_at=_ts(row["created_at"]) or "",
    ).model_dump()


def _require_db():
    if not db_configured():
        raise error_response(503, "Database not configured")


def _parse_uuid(value: str, label: str = "ID") -> uuid.UUID:
    """Parse a string as UUID, raising 400 if invalid."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise error_response(400, f"Invalid {label}: {value}")


# ---------------------------------------------------------------------------
# Mandate CRUD
# ---------------------------------------------------------------------------

@router.post("/mandates")
async def create_mandate(
    body: MandateCreate,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_mandate_write_limit),
):
    """Create a new purchase mandate."""
    _require_db()

    # Dynamic mandate limit based on subscription plan
    mandate_limit = await get_user_mandate_limit(user_id)

    async with get_conn() as conn:
        # Check mandate limit
        count = await conn.fetchval(
            "SELECT count(*) FROM public.purchase_mandates WHERE user_id = $1 AND status IN ('active','paused')",
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
        )
        if count >= mandate_limit:
            raise error_response(409, f"Mandate limit reached ({mandate_limit}). Upgrade your plan or delete existing mandates.")

        expires_at = None
        if body.expires_at:
            try:
                expires_at = datetime.fromisoformat(body.expires_at.replace("Z", "+00:00"))
            except ValueError:
                raise error_response(400, "Invalid expires_at format")

        row = await conn.fetchrow(
            """
            INSERT INTO public.purchase_mandates (
                user_id, name, search_query, category,
                condition_filter, min_trust_score,
                max_price, max_total_budget, cooldown_hours,
                allowed_sources, exclude_keywords, region, expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING """ + _MANDATE_COLUMNS + """
            """,
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
            body.name,
            body.search_query,
            body.category,
            body.condition_filter,
            body.min_trust_score,
            body.max_price,
            body.max_total_budget,
            body.cooldown_hours,
            body.allowed_sources,
            body.exclude_keywords,
            body.region,
            expires_at,
        )

    # Record demand signal with geo enrichment (best-effort, non-blocking)
    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="mandate_created",
            category=body.category,
            item_key=body.search_query,
            user_id=user_id,
            region=region,
            country_code=country,
        )
    except Exception as exc:
        logger.debug("[purchase] Demand signal recording failed: %s", exc)

    return _row_to_mandate(row)


@router.get("/mandates")
async def list_mandates(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """List all mandates for the current user."""
    _require_db()
    limit, offset = pagination

    async with get_conn() as conn:
        uid = uuid.UUID(user_id) if _is_uuid(user_id) else user_id
        total = await conn.fetchval(
            # Archived == deleted by the user. Without this filter a deleted
            # mandate stayed in the list, so delete looked like a no-op.
            "SELECT count(*) FROM public.purchase_mandates "
            "WHERE user_id = $1 AND status <> 'archived'",
            uid,
        )
        rows = await conn.fetch(
            f"""
            SELECT {_MANDATE_COLUMNS} FROM public.purchase_mandates
            WHERE user_id = $1 AND status <> 'archived'
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            uid, limit, offset,
        )

    return MandateListResponse(
        mandates=[_row_to_mandate(r) for r in rows],
        total=total,
    ).model_dump()


@router.get("/mandates/{mandate_id}")
async def get_mandate(
    mandate_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a single mandate by ID."""
    _require_db()

    async with get_conn() as conn:
        row = await conn.fetchrow(
            f"SELECT {_MANDATE_COLUMNS} FROM public.purchase_mandates WHERE id = $1 AND user_id = $2",
            _parse_uuid(mandate_id, "mandate_id"),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
        )

    if not row:
        raise error_response(404, "Mandate not found")
    return _row_to_mandate(row)


@router.patch("/mandates/{mandate_id}")
async def update_mandate(
    mandate_id: str,
    body: MandateUpdate,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_mandate_write_limit),
):
    """Update a mandate (pause/resume/edit criteria)."""
    _require_db()

    # Build dynamic SET clause from non-None fields (whitelist only)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise error_response(400, "No fields to update")

    # Reject any keys not in the whitelist
    bad_keys = set(updates.keys()) - _UPDATABLE_MANDATE_COLUMNS
    if bad_keys:
        raise error_response(400, f"Cannot update fields: {bad_keys}")

    # Handle expires_at parsing
    if "expires_at" in updates and updates["expires_at"]:
        try:
            updates["expires_at"] = datetime.fromisoformat(
                updates["expires_at"].replace("Z", "+00:00")
            )
        except ValueError:
            raise error_response(400, "Invalid expires_at format")

    set_parts = []
    params = []
    idx = 3  # $1=mandate_id, $2=user_id

    for key, val in updates.items():
        if key not in _UPDATABLE_MANDATE_COLUMNS:
            raise error_response(400, f"Unexpected column: {key}")
        set_parts.append(f"{key} = ${idx}")
        params.append(val)
        idx += 1

    set_parts.append(f"updated_at = ${idx}")
    params.append(datetime.now(timezone.utc))

    query = f"""
        UPDATE public.purchase_mandates
        SET {', '.join(set_parts)}
        WHERE id = $1 AND user_id = $2
        RETURNING {_MANDATE_COLUMNS}
    """

    async with get_conn() as conn:
        row = await conn.fetchrow(
            query,
            _parse_uuid(mandate_id, "mandate_id"),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
            *params,
        )

    if not row:
        raise error_response(404, "Mandate not found")
    return _row_to_mandate(row)


@router.delete("/mandates/{mandate_id}")
async def delete_mandate(
    mandate_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_mandate_write_limit),
):
    """Soft-delete a mandate by setting status='archived'.

    NOT 'paused'. Pausing is a distinct thing the user can do deliberately: the
    mandate stays listed, keeps its slot, and can be resumed. Deleting must
    free the slot. Reusing 'paused' for both meant a free user (limit 3) who
    deleted all three mandates could never create another — the create-limit
    counts status IN ('active','paused') — and the 409 told them to "delete
    existing mandates", which is exactly what they had just done.
    'archived' sits outside that set, so the slot is released.
    """
    _require_db()

    async with get_conn() as conn:
        result = await conn.execute(
            """
            UPDATE public.purchase_mandates
            SET status = 'archived', updated_at = now()
            WHERE id = $1 AND user_id = $2
            """,
            _parse_uuid(mandate_id, "mandate_id"),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
        )

    if result == "UPDATE 0":
        raise error_response(404, "Mandate not found")
    return {"ok": True, "id": mandate_id, "status": "paused"}


# ---------------------------------------------------------------------------
# Deal Endpoints
# ---------------------------------------------------------------------------

@router.get("/deals")
async def list_deals(
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    status: Optional[str] = Query(None, description="Filter by deal status"),
    _plan: str = Depends(require_plan("pro")),
):
    """List deals across all mandates for the current user. Pro+."""
    _require_db()
    limit, offset = pagination
    uid = uuid.UUID(user_id) if _is_uuid(user_id) else user_id

    async with get_conn() as conn:
        if status:
            if status not in _VALID_DEAL_STATUSES:
                raise error_response(400, f"Invalid status filter: {status}")
            total = await conn.fetchval(
                "SELECT count(*) FROM public.mandate_deals WHERE user_id = $1 AND status = $2",
                uid, status,
            )
            rows = await conn.fetch(
                f"""
                SELECT {_DEAL_COLUMNS} FROM public.mandate_deals
                WHERE user_id = $1 AND status = $2
                ORDER BY discovered_at DESC
                LIMIT $3 OFFSET $4
                """,
                uid, status, limit, offset,
            )
        else:
            total = await conn.fetchval(
                "SELECT count(*) FROM public.mandate_deals WHERE user_id = $1",
                uid,
            )
            rows = await conn.fetch(
                f"""
                SELECT {_DEAL_COLUMNS} FROM public.mandate_deals
                WHERE user_id = $1
                ORDER BY discovered_at DESC
                LIMIT $2 OFFSET $3
                """,
                uid, limit, offset,
            )

    return DealListResponse(
        deals=[_row_to_deal(r) for r in rows],
        total=total,
    ).model_dump()


@router.get("/deals/{deal_id}")
async def get_deal(
    deal_id: str,
    user_id: str = Depends(get_current_user_id),
    _plan: str = Depends(require_plan("pro")),
):
    """Get a single deal by ID. Pro+."""
    _require_db()

    async with get_conn() as conn:
        row = await conn.fetchrow(
            f"SELECT {_DEAL_COLUMNS} FROM public.mandate_deals WHERE id = $1 AND user_id = $2",
            _parse_uuid(deal_id, "deal_id"),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
        )

    if not row:
        raise error_response(404, "Deal not found")
    return _row_to_deal(row)


@router.post("/deals/{deal_id}/click")
async def click_deal(
    deal_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Track affiliate click — sets clicked_at and affiliate_click=true."""
    _require_db()

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE public.mandate_deals
            SET status = 'clicked',
                clicked_at = now(),
                affiliate_click = true
            WHERE id = $1 AND user_id = $2
              AND status = ANY($3::text[])
            RETURNING id, affiliate_url, listing_url
            """,
            _parse_uuid(deal_id, "deal_id"),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
            list(_CLICKABLE_STATUSES),
        )

    if not row:
        raise error_response(404, "Deal not found or not clickable")
    return {
        "ok": True,
        "id": str(row["id"]),
        "url": row["affiliate_url"] or row["listing_url"],
    }


@router.post("/deals/{deal_id}/confirm")
async def confirm_deal(
    deal_id: str,
    body: DealConfirmBody,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_deal_confirm_limit),
):
    """User confirms purchase ('I got it' + optional price paid)."""
    _require_db()
    uid = uuid.UUID(user_id) if _is_uuid(user_id) else user_id

    async with get_conn() as conn:
        # Status gate + idempotency: only confirm deals in confirmable states
        row = await conn.fetchrow(
            f"""
            SELECT {_DEAL_COLUMNS} FROM public.mandate_deals
            WHERE id = $1 AND user_id = $2 AND status = ANY($3::text[])
            """,
            _parse_uuid(deal_id, "deal_id"),
            uid,
            list(_CONFIRMABLE_STATUSES),
        )

        if not row:
            raise error_response(404, "Deal not found or already purchased/declined")

        # D3: a price of 0 (allowed by the ge=0 model bound) would inflate the
        # "saved vs market" stat by the full predicted q50. Reject explicitly —
        # a real purchase has a positive price; omit the field to default to the
        # listing price instead.
        if body.confirmed_price is not None and body.confirmed_price <= 0:
            raise error_response(400, "confirmed_price must be greater than 0")

        confirmed_price = body.confirmed_price if body.confirmed_price is not None else float(row["listing_price"])

        # Atomically set deal as purchased (idempotent via status gate above)
        result = await conn.execute(
            """
            UPDATE public.mandate_deals
            SET status = 'purchased',
                purchased_at = now(),
                confirmed_price = $3
            WHERE id = $1 AND user_id = $2
              AND status = ANY($4::text[])
            """,
            _parse_uuid(deal_id, "deal_id"),
            uid,
            confirmed_price,
            list(_CONFIRMABLE_STATUSES),
        )

        if result == "UPDATE 0":
            raise error_response(409, "Deal state changed concurrently")

        # Update mandate counters — IDOR fix: verify user_id owns the mandate
        await conn.execute(
            """
            UPDATE public.purchase_mandates
            SET deals_purchased = deals_purchased + 1,
                spent_total = spent_total + $3,
                updated_at = now()
            WHERE id = $1 AND user_id = $2
            """,
            row["mandate_id"],
            uid,
            confirmed_price,
        )

        # Check if mandate budget is exhausted (scoped to user_id)
        mandate = await conn.fetchrow(
            "SELECT max_total_budget, spent_total FROM public.purchase_mandates WHERE id = $1 AND user_id = $2",
            row["mandate_id"],
            uid,
        )
        if mandate and mandate["max_total_budget"] is not None:
            if float(mandate["spent_total"]) >= float(mandate["max_total_budget"]):
                await conn.execute(
                    "UPDATE public.purchase_mandates SET status = 'exhausted', updated_at = now() WHERE id = $1 AND user_id = $2",
                    row["mandate_id"],
                    uid,
                )

    return {
        "ok": True,
        "id": deal_id,
        "status": "purchased",
        "confirmed_price": confirmed_price,
    }


@router.post("/deals/{deal_id}/decline")
async def decline_deal(
    deal_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """User dismisses a deal."""
    _require_db()

    async with get_conn() as conn:
        result = await conn.execute(
            """
            UPDATE public.mandate_deals
            SET status = 'declined'
            WHERE id = $1 AND user_id = $2
              AND status = ANY($3::text[])
            """,
            _parse_uuid(deal_id, "deal_id"),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
            list(_DECLINABLE_STATUSES),
        )

    if result == "UPDATE 0":
        raise error_response(404, "Deal not found or not declinable")
    return {"ok": True, "id": deal_id, "status": "declined"}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_stats(
    user_id: str = Depends(get_current_user_id),
):
    """Get agent stats for the current user."""
    _require_db()
    uid = uuid.UUID(user_id) if _is_uuid(user_id) else user_id

    async with get_conn() as conn:
        active = await conn.fetchval(
            "SELECT count(*) FROM public.purchase_mandates WHERE user_id = $1 AND status = 'active'",
            uid,
        )
        deal_stats = await conn.fetchrow(
            """
            SELECT
                count(*) AS total_found,
                count(*) FILTER (WHERE affiliate_click = true) AS total_clicked,
                count(*) FILTER (WHERE status = 'purchased') AS total_purchased,
                -- D3: clamp per-deal savings at 0 with GREATEST so a bad buy
                -- (paid ABOVE predicted q50) can't subtract from the headline
                -- "saved vs market" stat — only genuine savings sum in.
                coalesce(sum(
                    CASE WHEN status = 'purchased' AND predicted_q50 IS NOT NULL
                    THEN GREATEST(0, predicted_q50 - coalesce(confirmed_price, listing_price))
                    ELSE 0 END
                ), 0) AS saved_vs_q50
            FROM public.mandate_deals
            WHERE user_id = $1
            """,
            uid,
        )

    return StatsResponse(
        active_mandates=active or 0,
        total_deals_found=deal_stats["total_found"] if deal_stats else 0,
        total_deals_clicked=deal_stats["total_clicked"] if deal_stats else 0,
        total_deals_purchased=deal_stats["total_purchased"] if deal_stats else 0,
        total_saved_vs_q50=round(float(deal_stats["saved_vs_q50"]), 2) if deal_stats else 0.0,
    ).model_dump()


class ForecastResponse(BaseModel):
    mandate_id: str
    remaining_budget: Optional[float] = None
    avg_deal_price: Optional[float] = None
    estimated_deals_left: Optional[int] = None
    total_deals_found: int = 0
    total_deals_purchased: int = 0
    spent_total: float = 0.0
    max_total_budget: Optional[float] = None


@router.get("/mandates/{mandate_id}/forecast")
async def forecast_mandate(
    mandate_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Budget forecast for a mandate: remaining budget, avg deal price, estimated deals left."""
    _require_db()
    uid = uuid.UUID(user_id) if _is_uuid(user_id) else user_id

    async with get_conn() as conn:
        mandate = await conn.fetchrow(
            f"SELECT {_MANDATE_COLUMNS} FROM public.purchase_mandates WHERE id = $1 AND user_id = $2",
            _parse_uuid(mandate_id, "mandate_id"), uid,
        )
        if not mandate:
            raise error_response(404, "Mandate not found")

        # Calculate avg deal price from purchased deals
        avg_row = await conn.fetchrow(
            """
            SELECT
                avg(coalesce(confirmed_price, listing_price)) AS avg_price,
                count(*) AS deal_count
            FROM public.mandate_deals
            WHERE mandate_id = $1 AND status = 'purchased'
            """,
            _parse_uuid(mandate_id, "mandate_id"),
        )

    spent = float(mandate.get("spent_total") or 0)
    max_budget = float(mandate["max_total_budget"]) if mandate.get("max_total_budget") else None
    remaining = (max_budget - spent) if max_budget is not None else None

    avg_price = float(avg_row["avg_price"]) if avg_row and avg_row["avg_price"] else None
    deal_count = int(avg_row["deal_count"]) if avg_row else 0

    estimated_left = None
    if remaining is not None and avg_price and avg_price > 0:
        estimated_left = max(0, int(remaining / avg_price))

    return ForecastResponse(
        mandate_id=mandate_id,
        remaining_budget=round(remaining, 2) if remaining is not None else None,
        avg_deal_price=round(avg_price, 2) if avg_price else None,
        estimated_deals_left=estimated_left,
        total_deals_found=int(mandate.get("deals_found") or 0),
        total_deals_purchased=deal_count,
        spent_total=round(spent, 2),
        max_total_budget=round(max_budget, 2) if max_budget is not None else None,
    ).model_dump()


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False
