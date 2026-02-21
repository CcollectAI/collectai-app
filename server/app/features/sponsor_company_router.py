"""
Sponsor company router — CRUD for external sponsor companies that pay to host events.

Endpoints:
    POST   /sponsor-companies            — Register a new sponsor company
    GET    /sponsor-companies/mine        — List companies owned by current user
    GET    /sponsor-companies/{id}        — Public company profile
    PATCH  /sponsor-companies/{id}        — Update company (admin only)
    POST   /sponsor-companies/{id}/create-event-checkout — Stripe checkout for sponsored event
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response

router = APIRouter(prefix="/sponsor-companies", tags=["sponsor-companies"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db_pool():
    try:
        from app.db import get_pool
        return get_pool()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateSponsorCompanyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=2048)
    website_url: Optional[str] = Field(None, max_length=2048)
    contact_email: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class UpdateSponsorCompanyRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=2048)
    website_url: Optional[str] = Field(None, max_length=2048)
    contact_email: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class SponsorCompanyResponse(BaseModel):
    id: str
    name: str
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    contact_email: str
    description: Optional[str] = None
    admin_user_id: str
    is_verified: bool = False
    created_at: Optional[str] = None


class CreateSponsorEventCheckoutRequest(BaseModel):
    tier: str = Field(..., pattern=r"^(featured|promoted|spotlight)$")
    event_title: str = Field(..., min_length=1, max_length=255)
    event_kind: str = Field(..., pattern=r"^(collection_drop|meetup|stream|convention|release)$")
    event_category_id: Optional[str] = Field(None, max_length=64)
    event_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    event_time: Optional[str] = Field(None, max_length=10)
    event_end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    event_location: Optional[str] = Field(None, max_length=500)
    event_online_url: Optional[str] = Field(None, max_length=2048)
    event_description: str = Field(default="", max_length=5000)
    event_image_url: Optional[str] = Field(None, max_length=2048)
    event_format: str = Field(default="in_person", pattern=r"^(in_person|online|hybrid)$")
    event_max_attendees: Optional[int] = Field(None, ge=1)


_UPDATABLE_COLUMNS = {"name", "logo_url", "website_url", "contact_email", "description"}

# Sponsor tier pricing (Stripe price IDs — placeholder until configured)
_TIER_PRICES = {
    "featured": "price_sponsor_featured",
    "promoted": "price_sponsor_promoted",
    "spotlight": "price_sponsor_spotlight",
}


def _row_to_company(row: dict[str, Any]) -> SponsorCompanyResponse:
    return SponsorCompanyResponse(
        id=str(row["id"]),
        name=row["name"],
        logo_url=row.get("logo_url"),
        website_url=row.get("website_url"),
        contact_email=row["contact_email"],
        description=row.get("description"),
        admin_user_id=str(row["admin_user_id"]),
        is_verified=row.get("is_verified", False),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/mine", response_model=List[SponsorCompanyResponse])
async def list_my_companies(
    user_id: str = Depends(get_current_user_id),
):
    """List sponsor companies where current user is admin."""
    pool = _get_db_pool()
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM sponsor_companies WHERE admin_user_id = $1 ORDER BY created_at DESC",
                user_id,
            )
            return [_row_to_company(dict(r)) for r in rows]
    except Exception as e:
        logger.error("[sponsor] Error listing companies: %s", e)
        raise error_response(500, "Failed to list companies", code="SPONSOR_LIST_ERROR")


@router.post("", response_model=SponsorCompanyResponse, status_code=201)
async def register_company(
    request: CreateSponsorCompanyRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Register a new sponsor company."""
    pool = _get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sponsor_companies (name, logo_url, website_url, contact_email, description, admin_user_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                request.name, request.logo_url, request.website_url,
                request.contact_email, request.description, user_id,
            )
            return _row_to_company(dict(row))
    except Exception as e:
        logger.error("[sponsor] Error registering company: %s", e)
        raise error_response(500, "Failed to register company", code="SPONSOR_CREATE_ERROR")


@router.get("/{company_id}", response_model=SponsorCompanyResponse)
async def get_company(company_id: str):
    """Get public sponsor company profile."""
    pool = _get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sponsor_companies WHERE id = $1", company_id,
            )
            if not row:
                raise error_response(404, "Company not found", code="SPONSOR_NOT_FOUND")
            return _row_to_company(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[sponsor] Error fetching company %s: %s", company_id, e)
        raise error_response(500, "Failed to fetch company", code="SPONSOR_FETCH_ERROR")


@router.patch("/{company_id}", response_model=SponsorCompanyResponse)
async def update_company(
    company_id: str,
    request: UpdateSponsorCompanyRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Update a sponsor company (admin_user_id only)."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise error_response(400, "No fields to update", code="NO_FIELDS")

    bad_keys = set(updates.keys()) - _UPDATABLE_COLUMNS
    if bad_keys:
        raise error_response(400, f"Cannot update: {', '.join(sorted(bad_keys))}", code="INVALID_FIELDS")

    pool = _get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sponsor_companies WHERE id = $1 AND admin_user_id = $2",
                company_id, user_id,
            )
            if not row:
                raise error_response(404, "Company not found or not owned by you", code="SPONSOR_NOT_FOUND")

            set_parts = []
            params = [company_id, user_id]
            idx = 3
            for key, val in updates.items():
                set_parts.append(f"{key} = ${idx}")
                params.append(val)
                idx += 1
            set_parts.append(f"updated_at = ${idx}")
            params.append(datetime.now(timezone.utc))

            query = f"""
                UPDATE sponsor_companies SET {', '.join(set_parts)}
                WHERE id = $1 AND admin_user_id = $2
                RETURNING *
            """
            updated = await conn.fetchrow(query, *params)
            if not updated:
                raise error_response(404, "Company not found", code="SPONSOR_NOT_FOUND")
            return _row_to_company(dict(updated))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[sponsor] Error updating company %s: %s", company_id, e)
        raise error_response(500, "Failed to update company", code="SPONSOR_UPDATE_ERROR")


@router.post("/{company_id}/create-event-checkout")
async def create_event_checkout(
    company_id: str,
    request: CreateSponsorEventCheckoutRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a Stripe Checkout Session for a sponsored event."""
    pool = _get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # Verify company ownership
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sponsor_companies WHERE id = $1 AND admin_user_id = $2",
                company_id, user_id,
            )
            if not row:
                raise error_response(404, "Company not found or not owned by you", code="SPONSOR_NOT_FOUND")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[sponsor] Error verifying company %s: %s", company_id, e)
        raise error_response(500, "Failed to verify company", code="SPONSOR_VERIFY_ERROR")

    company = dict(row)

    # Create the event first as draft
    try:
        async with pool.acquire() as conn:
            ev_row = await conn.fetchrow(
                """
                INSERT INTO events (
                    title, kind, category_id, date, time, end_date,
                    location, online_url, description, image_url,
                    format, status, is_public, max_attendees,
                    source, created_by, sponsor_company_id,
                    is_sponsored, sponsor_name, sponsor_logo_url, sponsor_tier
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, 'draft', true, $12, 'sponsor', $13, $14,
                        false, $15, $16, $17)
                RETURNING id
                """,
                request.event_title, request.event_kind, request.event_category_id,
                request.event_date, request.event_time, request.event_end_date,
                request.event_location, request.event_online_url, request.event_description,
                request.event_image_url, request.event_format, request.event_max_attendees,
                user_id, company_id,
                company["name"], company.get("logo_url"), request.tier,
            )
            event_id = str(ev_row["id"])
    except Exception as e:
        logger.error("[sponsor] Error creating draft event: %s", e)
        raise error_response(500, "Failed to create event", code="SPONSOR_EVENT_ERROR")

    # Create Stripe checkout session
    try:
        from app.config import STRIPE_SECRET_KEY
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        if not STRIPE_SECRET_KEY:
            raise error_response(503, "Billing not configured")

        price_id = _TIER_PRICES.get(request.tier)
        if not price_id:
            raise error_response(400, f"Invalid tier: {request.tier}")

        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            success_url=f"collectai://sponsor/dashboard?checkout=success&event_id={event_id}",
            cancel_url="collectai://sponsor/dashboard?checkout=cancel",
            metadata={
                "type": "event_sponsor",
                "event_id": event_id,
                "company_id": company_id,
                "tier": request.tier,
                "sponsor_name": company["name"],
                "user_id": user_id,
            },
        )
        return {"url": session.url, "session_id": session.id, "event_id": event_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[sponsor] Stripe checkout creation failed: %s", e)
        raise error_response(500, "Failed to create checkout session", code="STRIPE_ERROR")
