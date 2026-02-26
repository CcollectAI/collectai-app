"""
Sponsor router — Stripe one-time payments for sponsored event placement.

Endpoints:
    POST /events/sponsor-checkout — Create a Stripe one-time payment session for event sponsorship
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.config import (
    DB_ENABLED,
    STRIPE_SECRET_KEY,
    STRIPE_PRICE_ID_SPONSOR_FEATURED,
    STRIPE_PRICE_ID_SPONSOR_PROMOTED,
    STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT,
    SPONSOR_TIER_BASIC,
    SPONSOR_TIER_PRO,
    SPONSOR_TIER_PREMIUM,
)
from app.db import get_pool
from app.errors import error_response

_log = logging.getLogger("collectai.sponsor")

router = APIRouter(prefix="/events", tags=["events"])

# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

SPONSOR_TIERS = {
    "featured": {
        "label": "Featured Event",
        "price_cents": SPONSOR_TIER_BASIC,
        "price_id_env": "STRIPE_PRICE_ID_SPONSOR_FEATURED",
    },
    "promoted": {
        "label": "Promoted Event",
        "price_cents": SPONSOR_TIER_PRO,
        "price_id_env": "STRIPE_PRICE_ID_SPONSOR_PROMOTED",
    },
    "spotlight": {
        "label": "Spotlight Package",
        "price_cents": SPONSOR_TIER_PREMIUM,
        "price_id_env": "STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT",
    },
}

_TIER_PRICE_IDS = {
    "featured": STRIPE_PRICE_ID_SPONSOR_FEATURED,
    "promoted": STRIPE_PRICE_ID_SPONSOR_PROMOTED,
    "spotlight": STRIPE_PRICE_ID_SPONSOR_SPOTLIGHT,
}

# ---------------------------------------------------------------------------
# Lazy Stripe import
# ---------------------------------------------------------------------------

_stripe: Any = None


def _get_stripe():
    global _stripe
    if _stripe is None:
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            _stripe = stripe
        except ImportError:
            _stripe = False
    if _stripe is False:
        return None
    return _stripe


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class SponsorCheckoutRequest(BaseModel):
    event_id: str = Field(..., min_length=1)
    tier: str = Field(..., pattern=r"^(featured|promoted|spotlight)$")
    sponsor_name: str = Field(..., min_length=1, max_length=255)


# ---------------------------------------------------------------------------
# POST /events/sponsor-checkout
# ---------------------------------------------------------------------------


@router.post("/sponsor-checkout")
async def create_sponsor_checkout(
    body: SponsorCheckoutRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a Stripe Checkout session for sponsoring an event."""
    stripe_mod = _get_stripe()
    if not stripe_mod or not STRIPE_SECRET_KEY:
        raise error_response(503, "Billing not configured")

    if not DB_ENABLED:
        raise error_response(503, "Database not available")

    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available")

    # Validate event exists and user owns it
    row = await pool.fetchrow(
        "SELECT id, created_by, is_sponsored FROM events WHERE id = $1",
        body.event_id,
    )
    if row is None:
        raise error_response(404, "Event not found", code="EVENT_NOT_FOUND")

    if str(row["created_by"]) != user_id:
        raise error_response(403, "You can only sponsor your own events", code="NOT_OWNER")

    if row["is_sponsored"]:
        raise error_response(409, "Event is already sponsored", code="ALREADY_SPONSORED")

    # Get Stripe price ID for the tier
    price_id = _TIER_PRICE_IDS.get(body.tier, "")
    if not price_id:
        raise error_response(503, f"Stripe price not configured for tier '{body.tier}'")

    try:
        session = stripe_mod.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            success_url=f"collectai://events/{body.event_id}?sponsor=success",
            cancel_url=f"collectai://events/{body.event_id}?sponsor=cancel",
            metadata={
                "type": "event_sponsor",
                "event_id": body.event_id,
                "tier": body.tier,
                "sponsor_name": body.sponsor_name,
                "user_id": user_id,
            },
        )
        return JSONResponse({"url": session.url, "session_id": session.id})
    except Exception:
        _log.exception("Stripe sponsor checkout session creation failed")
        raise error_response(500, "Failed to create checkout session")
