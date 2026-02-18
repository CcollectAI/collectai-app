"""
Billing router — Stripe checkout sessions, webhook, and subscription status.

Endpoints:
    POST /billing/checkout-session  — Create a Stripe Checkout session for plan upgrade
    POST /billing/portal-session    — Create a Stripe Customer Portal session (manage/cancel)
    GET  /billing/status            — Return current user's subscription status
    POST /billing/webhook           — Stripe webhook (no auth — signature verified)
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.auth import get_current_user_id
from app.config import (
    DB_ENABLED,
    DEV_MODE,
    STRIPE_PRICE_ID_PREMIUM,
    STRIPE_PRICE_ID_PRO,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    SUPABASE_URL,
)
from app.db import get_pool
from app.errors import error_response

_log = logging.getLogger("collectai.billing")

router = APIRouter(prefix="/billing", tags=["billing"])

# ---------------------------------------------------------------------------
# Lazy Stripe import (optional dependency)
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
            _stripe = False  # sentinel: not installed
    if _stripe is False:
        return None
    return _stripe


# ---------------------------------------------------------------------------
# Plan → price ID mapping
# ---------------------------------------------------------------------------

_PLAN_PRICES = {
    "pro": STRIPE_PRICE_ID_PRO,
    "premium": STRIPE_PRICE_ID_PREMIUM,
}

PLAN_LIMITS = {
    "free": {"max_mandates": 3, "deal_discovery": False, "dossier_pdf": False, "advanced_analytics": False},
    "pro": {"max_mandates": 10, "deal_discovery": True, "dossier_pdf": True, "advanced_analytics": False},
    "premium": {"max_mandates": 50, "deal_discovery": True, "dossier_pdf": True, "advanced_analytics": True},
}

# ---------------------------------------------------------------------------
# Webhook idempotency — bounded LRU of processed event IDs
# ---------------------------------------------------------------------------

_SEEN_EVENTS: OrderedDict[str, float] = OrderedDict()
_MAX_SEEN = 500


def _event_already_processed(event_id: str) -> bool:
    """Return True if this Stripe event was already handled (dedup)."""
    if event_id in _SEEN_EVENTS:
        return True
    _SEEN_EVENTS[event_id] = time.monotonic()
    while len(_SEEN_EVENTS) > _MAX_SEEN:
        _SEEN_EVENTS.popitem(last=False)
    return False


def _safe_timestamp(ts: int | float | None) -> datetime | None:
    """Convert a Unix timestamp to datetime, returning None on failure."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_subscription(user_id: str) -> dict | None:
    """Fetch the subscription row for a user, or None."""
    if not DB_ENABLED:
        return None
    pool = get_pool()
    if pool is None:
        return None
    row = await pool.fetchrow(
        "SELECT plan, status, current_period_end, cancel_at_period_end, "
        "stripe_customer_id, stripe_subscription_id "
        "FROM subscriptions WHERE user_id = $1",
        user_id,
    )
    return dict(row) if row else None


async def _ensure_subscription_row(user_id: str) -> dict:
    """Return existing sub row or create a free-tier one."""
    sub = await _get_subscription(user_id)
    if sub:
        return sub
    pool = get_pool()
    if pool is None:
        return {"plan": "free", "status": "active"}
    row = await pool.fetchrow(
        "INSERT INTO subscriptions (user_id, plan, status) "
        "VALUES ($1, 'free', 'active') "
        "ON CONFLICT (user_id) DO UPDATE SET updated_at = now() "
        "RETURNING plan, status, current_period_end, cancel_at_period_end, "
        "stripe_customer_id, stripe_subscription_id",
        user_id,
    )
    return dict(row) if row else {"plan": "free", "status": "active"}


async def _get_or_create_stripe_customer(user_id: str, stripe_mod: Any) -> str:
    """Return existing Stripe customer ID or create one."""
    pool = get_pool()
    if pool is None:
        raise ValueError("Database not available")
    row = await pool.fetchrow(
        "SELECT stripe_customer_id FROM subscriptions WHERE user_id = $1",
        user_id,
    )
    if row and row["stripe_customer_id"]:
        return row["stripe_customer_id"]

    # Create Stripe customer
    customer = stripe_mod.Customer.create(metadata={"user_id": user_id})
    await pool.execute(
        "INSERT INTO subscriptions (user_id, stripe_customer_id, plan, status) "
        "VALUES ($1, $2, 'free', 'active') "
        "ON CONFLICT (user_id) DO UPDATE SET stripe_customer_id = $2, updated_at = now()",
        user_id,
        customer.id,
    )
    return customer.id


# ---------------------------------------------------------------------------
# POST /billing/checkout-session
# ---------------------------------------------------------------------------


@router.post("/checkout-session")
async def create_checkout_session(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Create a Stripe Checkout Session for upgrading to pro or premium."""
    stripe_mod = _get_stripe()
    if not stripe_mod or not STRIPE_SECRET_KEY:
        raise error_response(503, "Billing not configured")

    if not DB_ENABLED:
        raise error_response(503, "Database not available")

    body = await request.json()
    plan = body.get("plan", "").lower()
    if plan not in _PLAN_PRICES:
        raise error_response(400, f"Invalid plan: {plan}. Choose 'pro' or 'premium'.")

    price_id = _PLAN_PRICES[plan]
    if not price_id:
        raise error_response(503, f"Price ID not configured for plan '{plan}'")

    # Prevent duplicate checkout for already-subscribed users
    existing = await _get_subscription(user_id)
    if existing and existing.get("plan") == plan and existing.get("status") in ("active", "trialing"):
        raise error_response(409, f"You are already on the {plan} plan")

    try:
        customer_id = await _get_or_create_stripe_customer(user_id, stripe_mod)

        session = stripe_mod.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="collectai://subscription?checkout=success&session_id={CHECKOUT_SESSION_ID}",
            cancel_url="collectai://subscription?checkout=cancel",
            metadata={"user_id": user_id, "plan": plan},
        )
        return JSONResponse({"url": session.url, "session_id": session.id})
    except Exception as exc:
        _log.exception("Stripe checkout session creation failed")
        raise error_response(500, "Failed to create checkout session")


# ---------------------------------------------------------------------------
# POST /billing/portal-session
# ---------------------------------------------------------------------------


@router.post("/portal-session")
async def create_portal_session(
    user_id: str = Depends(get_current_user_id),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    stripe_mod = _get_stripe()
    if not stripe_mod or not STRIPE_SECRET_KEY:
        raise error_response(503, "Billing not configured")

    if not DB_ENABLED:
        raise error_response(503, "Database not available")

    sub = await _get_subscription(user_id)
    if not sub or not sub.get("stripe_customer_id"):
        raise error_response(404, "No billing account found. Subscribe first.")

    try:
        session = stripe_mod.billing_portal.Session.create(
            customer=sub["stripe_customer_id"],
            return_url="collectai://settings",
        )
        return JSONResponse({"url": session.url})
    except Exception as exc:
        _log.exception("Stripe portal session creation failed")
        raise error_response(500, "Failed to create portal session")


# ---------------------------------------------------------------------------
# GET /billing/status
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_billing_status(
    user_id: str = Depends(get_current_user_id),
):
    """Return the current user's subscription plan, status, and feature limits."""
    if DEV_MODE and not DB_ENABLED:
        return JSONResponse({
            "plan": "premium",
            "status": "active",
            "limits": PLAN_LIMITS["premium"],
            "cancel_at_period_end": False,
        })

    sub = await _ensure_subscription_row(user_id)
    plan = sub.get("plan", "free")
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    return JSONResponse({
        "plan": plan,
        "status": sub.get("status", "active"),
        "current_period_end": sub.get("current_period_end", None),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "limits": limits,
    })


# ---------------------------------------------------------------------------
# POST /billing/webhook
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events (no auth — verified via signature)."""
    stripe_mod = _get_stripe()
    if not stripe_mod or not STRIPE_WEBHOOK_SECRET:
        raise error_response(503, "Webhook not configured")

    payload = await request.body()

    try:
        event = stripe_mod.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        _log.warning("Invalid Stripe webhook signature")
        return JSONResponse({"error": "Invalid signature"}, status_code=400)
    except Exception as exc:
        # Covers stripe.error.SignatureVerificationError and other Stripe errors
        if "Signature" in type(exc).__name__ or "signature" in str(exc).lower():
            _log.warning("Invalid Stripe webhook signature: %s", exc)
            return JSONResponse({"error": "Invalid signature"}, status_code=400)
        raise

    event_id = event.get("id", "")
    if _event_already_processed(event_id):
        _log.info("Stripe webhook duplicate skipped: %s", event_id)
        return JSONResponse({"received": True, "duplicate": True})

    event_type = event["type"]
    data = event["data"]["object"]
    _log.info("Stripe webhook: %s (id=%s)", event_type, event_id)

    pool = get_pool()
    if pool is None:
        _log.warning("Stripe webhook received but DB is not available")
        return JSONResponse({"received": True})

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(pool, data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(pool, data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(pool, data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(pool, data)

    return JSONResponse({"received": True})


# ---------------------------------------------------------------------------
# Webhook event handlers
# ---------------------------------------------------------------------------


async def _handle_checkout_completed(pool: Any, session: dict):
    """After successful checkout, link subscription to user."""
    user_id = session.get("metadata", {}).get("user_id")
    plan = session.get("metadata", {}).get("plan", "pro")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        _log.warning("checkout.session.completed missing user_id in metadata")
        return

    await pool.execute(
        """
        INSERT INTO subscriptions (user_id, stripe_customer_id, stripe_subscription_id, plan, status)
        VALUES ($1, $2, $3, $4, 'active')
        ON CONFLICT (user_id) DO UPDATE SET
            stripe_customer_id = $2,
            stripe_subscription_id = $3,
            plan = $4,
            status = 'active',
            updated_at = now()
        """,
        user_id,
        customer_id,
        subscription_id,
        plan,
    )
    _log.info("User %s subscribed to %s plan", user_id, plan)


async def _handle_subscription_updated(pool: Any, subscription: dict):
    """Subscription updated (plan change, renewal, etc.)."""
    sub_id = subscription.get("id")
    status = subscription.get("status", "active")
    cancel_at_period_end = subscription.get("cancel_at_period_end", False)
    current_period_start = subscription.get("current_period_start")
    current_period_end = subscription.get("current_period_end")

    # Map Stripe price to plan
    items = subscription.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = "free"  # default if price not recognised
    if price_id == STRIPE_PRICE_ID_PREMIUM:
        plan = "premium"
    elif price_id == STRIPE_PRICE_ID_PRO:
        plan = "pro"

    period_start = _safe_timestamp(current_period_start)
    period_end = _safe_timestamp(current_period_end)

    await pool.execute(
        """
        UPDATE subscriptions SET
            plan = $1, status = $2, cancel_at_period_end = $3,
            current_period_start = $4, current_period_end = $5, updated_at = now()
        WHERE stripe_subscription_id = $6
        """,
        plan,
        status,
        cancel_at_period_end,
        period_start,
        period_end,
        sub_id,
    )
    _log.info("Subscription %s updated: plan=%s status=%s", sub_id, plan, status)


async def _handle_subscription_deleted(pool: Any, subscription: dict):
    """Subscription cancelled — downgrade to free."""
    sub_id = subscription.get("id")
    await pool.execute(
        """
        UPDATE subscriptions SET plan = 'free', status = 'canceled', updated_at = now()
        WHERE stripe_subscription_id = $1
        """,
        sub_id,
    )
    _log.info("Subscription %s deleted — downgraded to free", sub_id)


async def _handle_payment_failed(pool: Any, invoice: dict):
    """Payment failed — mark subscription as past_due."""
    sub_id = invoice.get("subscription")
    if sub_id:
        await pool.execute(
            "UPDATE subscriptions SET status = 'past_due', updated_at = now() "
            "WHERE stripe_subscription_id = $1",
            sub_id,
        )
        _log.warning("Payment failed for subscription %s", sub_id)
