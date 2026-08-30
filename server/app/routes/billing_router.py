"""
Billing router — Stripe checkout sessions, webhook, and subscription status.

Endpoints:
    POST /billing/checkout-session  — Create a Stripe Checkout session for plan upgrade
    POST /billing/portal-session    — Create a Stripe Customer Portal session (manage/cancel)
    GET  /billing/status            — Return current user's subscription status
    POST /billing/webhook           — Stripe webhook (no auth — signature verified)
    POST /billing/revenuecat-webhook — RevenueCat webhook (no auth — shared-secret header)
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.auth import get_current_user_id
from app.config import (
    DB_ENABLED,
    DEV_MODE,
    STRIPE_PRICE_ID_PREMIUM,
    STRIPE_PRICE_ID_PRO,
    STRIPE_PRICE_PREMIUM_MONTHLY,
    STRIPE_PRICE_PREMIUM_YEARLY,
    STRIPE_PRICE_PRO_MONTHLY,
    STRIPE_PRICE_PRO_MONTHLY_WEB,
    STRIPE_PRICE_PRO_YEARLY,
    STRIPE_PRICE_PRO_YEARLY_WEB,
    STRIPE_SECRET_KEY,
    REVENUECAT_WEBHOOK_AUTH,
    STRIPE_WEBHOOK_SECRET,
    SUPABASE_URL,
)
from app.db import get_pool
from app.lib.json_safe import json_safe_value
from app.lib.revenuecat import (
    _RC_ACTIVE_EVENTS,
    _RC_ENDED_EVENTS,
    _rc_affiliate_code,
    _rc_ms_to_dt,
    _rc_plan_from_event,
    _rc_revenue_cents,
)
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

_log = logging.getLogger("collectai.billing")

router = APIRouter(prefix="/billing", tags=["Billing"])

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

# Centralized price resolution: monthly/yearly env vars take precedence over
# the legacy single-price-per-plan vars.  This lets you configure granular
# billing intervals while remaining backwards-compatible.
_PLAN_PRICES_BY_INTERVAL: dict[str, dict[str, str]] = {
    "pro": {
        "monthly": STRIPE_PRICE_PRO_MONTHLY or STRIPE_PRICE_ID_PRO,
        "yearly": STRIPE_PRICE_PRO_YEARLY or STRIPE_PRICE_ID_PRO,
    },
    "premium": {
        "monthly": STRIPE_PRICE_PREMIUM_MONTHLY or STRIPE_PRICE_ID_PREMIUM,
        "yearly": STRIPE_PRICE_PREMIUM_YEARLY or STRIPE_PRICE_ID_PREMIUM,
    },
}

# Legacy flat lookup (for webhook reverse mapping)
_PLAN_PRICES = {
    "pro": STRIPE_PRICE_ID_PRO,
    "premium": STRIPE_PRICE_ID_PREMIUM,
}

# Reverse lookup: price_id → plan name (includes all intervals)
_PRICE_TO_PLAN: dict[str, str] = {}
for _plan_name, _intervals in _PLAN_PRICES_BY_INTERVAL.items():
    for _price_id in _intervals.values():
        if _price_id:
            _PRICE_TO_PLAN[_price_id] = _plan_name


def _resolve_price_id(plan: str, interval: str = "monthly") -> str | None:
    """Resolve the Stripe Price ID for a given plan and billing interval.

    Returns None if no price ID is configured for the combination.
    """
    intervals = _PLAN_PRICES_BY_INTERVAL.get(plan)
    if not intervals:
        return None
    return intervals.get(interval) or intervals.get("monthly") or None

# Per-plan feature limits.
# Keys MUST match the BillingStatus['limits'] shape consumed by the FE in
# src/hooks/useBillingLimits.ts. The earlier dict was missing
# `condition_grading` and `set_completion`, so for every real paid user
# the FE read those as `undefined` (falsy) and showed locked UI on grading
# + sets-to-complete despite payment. Fixed 2026-05-01 to match the FE's
# DEFAULT_LIMITS / FORCED_LIMITS shape exactly.
#
# Tier breakdown (mirrors FORCED_LIMITS in src/hooks/useBillingLimits.ts):
#   free     : 0 mandates (deal discovery is Pro-only), 25 watchlist slots,
#              1 Target Hit/day, 1 price alert/week, ads on
#   pro      : 10 mandates, unlimited watchlist + alerts, dossier_pdf,
#              deal_discovery, condition_grading, set_completion, no ads.
#   premium  : 50 mandates + everything Pro has + advanced_analytics.
#
# Flag semantics:
#   advanced_analytics : the trend chart, item history and market prices on
#                        catalog-item, plus the analytics screen. Despite the
#                        name this is the PRO gate and always has been in code —
#                        `detailed_valuation` was the flag this block used to
#                        describe, and nothing ever read it (removed
#                        2026-08-16).
# NOTE (2026-08-16): `detailed_valuation` was removed from every plan. Nothing
# read it — not the server, not the client, and the FE limits tables never
# defined it. The q10/q50/q90 bands on catalog-item have always been gated by
# `advanced_analytics`; a comment claiming otherwise was corrected on
# 2026-07-28 but the dead key stayed in the payload, so /billing/status shipped
# a gate that gated nothing. Found by auditing every PLAN_LIMITS key for an
# enforcement site.
PLAN_LIMITS = {
    "free": {
        # 0, not 3. Deal discovery is Pro-only (the worker skips free users'
        # mandates entirely), so a mandate on the free plan can never produce
        # a deal — and the Home entry point already routes free users to the
        # paywall. Allotting 3 meant advertising 3 mandates that were
        # unreachable through the UI and inert if reached by deep link.
        # Changed 2026-07-31; MONETIZATION.md updated to match.
        "max_mandates": 0,
        # Watchlist size is the Pro lever for Target Hit: the alert can only
        # fire on something you are watching, so slots ARE reach. Added
        # 2026-08-06. None = unlimited.
        "max_watchlist_items": 25,
        # Target Hits per rolling 24h. deal_discovery_worker reads this — do
        # not re-declare the number in the worker.
        "max_daily_deal_alerts": 1,
        # Price-alert creation cap per rolling 7 days. None = unlimited.
        "max_alerts_per_week": 1,
        "deal_discovery": False,
        "dossier_pdf": False,
        "advanced_analytics": False,
        "condition_grading": False,
        "set_completion": False,
        "show_ads": True,
    },
    "pro": {
        "max_mandates": 10,
        "max_watchlist_items": None,
        "max_daily_deal_alerts": None,
        "max_alerts_per_week": None,
        "deal_discovery": True,
        "dossier_pdf": True,
        # True since 2026-07-28. This was False, a leftover from the old
        # three-tier model where advanced_analytics was Premium-only. Premium
        # was folded into Pro (docs/MONETIZATION.md) and is no longer
        # purchasable -- RevenueCat sells only the `pro` entitlement -- so
        # while this stayed False NO user could ever be granted it here.
        #
        # It disagreed with the front end, which has always had
        # FORCED_LIMITS.pro.advanced_analytics = true
        # (src/hooks/useBillingLimits.ts). On iOS that divergence is masked:
        # RevenueCat resolves the plan and the FE uses its own table. The BE
        # value is only consumed on the fallback path -- RevenueCat
        # unconfigured (no EXPO_PUBLIC_REVENUECAT_IOS_KEY) or reporting free --
        # and there a paying Pro user was told advanced_analytics=False, which
        # sends the Home "Extended Portfolio Insights" button to the paywall
        # instead of /analytics (app/(tabs)/index.tsx:470).
        #
        # No server route enforces this flag; it is reported to the client
        # only, so this changes what /billing/status advertises, nothing else.
        "advanced_analytics": True,
        "condition_grading": True,
        "set_completion": True,
        "show_ads": False,
    },
    "premium": {
        "max_mandates": 50,
        "max_watchlist_items": None,
        "max_daily_deal_alerts": None,
        "max_alerts_per_week": None,
        "deal_discovery": True,
        "dossier_pdf": True,
        "advanced_analytics": True,
        "condition_grading": True,
        "set_completion": True,
        "show_ads": False,
    },
}

# ---------------------------------------------------------------------------
# Webhook idempotency — bounded LRU of processed event IDs
# NOTE: This is per-process only. With multiple workers (uvicorn --workers N),
# duplicate events can still be processed by different workers. For production
# multi-worker deployments, use a DB-based idempotency table instead.
# ---------------------------------------------------------------------------

_SEEN_EVENTS: OrderedDict[str, float] = OrderedDict()
_MAX_SEEN = 5_000


def _event_already_processed_mem(event_id: str) -> bool:
    """In-memory LRU check (single-worker fallback)."""
    if event_id in _SEEN_EVENTS:
        return True
    _SEEN_EVENTS[event_id] = time.monotonic()
    while len(_SEEN_EVENTS) > _MAX_SEEN:
        _SEEN_EVENTS.popitem(last=False)
    return False


async def _event_already_processed(event_id: str, event_type: str, pool: Any | None) -> bool:
    """Check Stripe webhook idempotency — DB first, in-memory fallback.

    Uses the ``processed_webhook_events`` table for multi-worker dedup.
    Falls back to in-memory LRU if the table doesn't exist yet.
    """
    # Fast in-memory check first
    if event_id in _SEEN_EVENTS:
        return True

    if pool is not None:
        try:
            # Atomic claim: INSERT returns a row only when the event_id was new.
            # If another worker raced and won, the ON CONFLICT swallows our insert
            # and `claimed` is None — meaning the event was already processed.
            claimed = await pool.fetchrow(
                "INSERT INTO processed_webhook_events (event_id, event_type) "
                "VALUES ($1, $2) ON CONFLICT (event_id) DO NOTHING RETURNING event_id",
                event_id,
                event_type,
            )
            if claimed is None:
                _SEEN_EVENTS[event_id] = time.monotonic()
                return True
            return False
        except Exception as e:
            # Table may not exist yet — fall through to in-memory (single-worker only)
            _log.debug("DB webhook dedup unavailable, using in-memory: %s", e)

    return _event_already_processed_mem(event_id)


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
    """Return existing sub row or create a free-tier one.

    `subscriptions.user_id` is `REFERENCES auth.users(id) ON DELETE CASCADE`, so
    this INSERT raises for a token naming a user that does not exist. On
    2026-08-12 that happened 21 times in 24h, all for the synthetic uid
    `00000000-0000-0000-0000-0000000000aa`, reaching us through
    `GET /billing/status`. Every one of them landed in the Postgres log as an
    ERROR and NONE of them appeared in ours — which is precisely the diagnostic
    in docs/DEPLOYMENT.md ("an error Postgres reports that your application log
    does not contain"), except here the writer IS the app and the cause was
    simply never logged on this path.

    A subscription row cannot be created for a user that does not exist, and
    retrying will never help. Degrade to the free-tier default the caller would
    have got anyway, and log it ONCE at error level with the uid so the next
    person sees the responsible id in `bake.log` instead of inferring it from
    Supabase's Postgres logs.
    """
    sub = await _get_subscription(user_id)
    if sub:
        return sub
    pool = get_pool()
    if pool is None:
        return {"plan": "free", "status": "active"}
    try:
        row = await pool.fetchrow(
            "INSERT INTO subscriptions (user_id, plan, status) "
            "VALUES ($1, 'free', 'active') "
            "ON CONFLICT (user_id) DO UPDATE SET updated_at = now() "
            "RETURNING plan, status, current_period_end, cancel_at_period_end, "
            "stripe_customer_id, stripe_subscription_id",
            user_id,
        )
    except asyncpg.ForeignKeyViolationError:
        _log.error(
            "[billing] no auth.users row for %s — serving free tier without "
            "persisting. A token naming a deleted or synthetic user.",
            user_id,
        )
        return {"plan": "free", "status": "active"}
    return dict(row) if row else {"plan": "free", "status": "active"}


async def _get_or_create_stripe_customer(user_id: str, stripe_mod: Any) -> str:
    """Return existing Stripe customer ID or create one.

    Uses SELECT FOR UPDATE to prevent race conditions that could create
    duplicate Stripe customers when two requests arrive concurrently.
    """
    pool = get_pool()
    if pool is None:
        raise ValueError("Database not available")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock the row to prevent concurrent creation
            row = await conn.fetchrow(
                "SELECT stripe_customer_id FROM subscriptions WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if row and row["stripe_customer_id"]:
                return row["stripe_customer_id"]

            # No row or no stripe_customer_id — create Stripe customer off-thread
            customer = await asyncio.to_thread(
                stripe_mod.Customer.create, metadata={"user_id": user_id}
            )
            await conn.execute(
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


@router.post("/checkout-session", summary="Create checkout session")
async def create_checkout_session(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(10, scope="billing")),
):
    """Create a Stripe Checkout Session for upgrading to pro or premium."""
    stripe_mod = _get_stripe()
    if not stripe_mod or not STRIPE_SECRET_KEY:
        raise error_response(503, "Billing not configured")

    if not DB_ENABLED:
        raise error_response(503, "Database not available")

    body = await request.json()
    plan = body.get("plan", "").lower()
    interval = body.get("interval", "monthly").lower()
    if plan not in _PLAN_PRICES_BY_INTERVAL:
        raise error_response(400, f"Invalid plan: {plan}. Choose 'pro' or 'premium'.")
    if interval not in ("monthly", "yearly"):
        raise error_response(400, f"Invalid interval: {interval}. Choose 'monthly' or 'yearly'.")

    price_id = _resolve_price_id(plan, interval)
    if not price_id:
        raise error_response(
            503,
            f"Stripe Price ID not configured for {plan}/{interval}. "
            f"Set STRIPE_PRICE_{plan.upper()}_{'MONTHLY' if interval == 'monthly' else 'YEARLY'} "
            f"in your environment variables.",
        )

    # Prevent duplicate checkout for already-subscribed users
    existing = await _get_subscription(user_id)
    if existing and existing.get("plan") == plan and existing.get("status") in ("active", "trialing"):
        raise error_response(409, f"You are already on the {plan} plan")

    try:
        customer_id = await _get_or_create_stripe_customer(user_id, stripe_mod)

        session = await asyncio.to_thread(
            stripe_mod.checkout.Session.create,
            customer=customer_id,
            # Let Stripe auto-detect payment methods (card, iDEAL, Bancontact, SEPA, etc.)
            # based on customer location and currency.
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="collectai://subscription?checkout=success&session_id={CHECKOUT_SESSION_ID}",
            cancel_url="collectai://subscription?checkout=cancel",
            metadata={"user_id": user_id, "plan": plan},
        )
        return JSONResponse({"url": session.url, "session_id": session.id})
    except stripe_mod.error.StripeError as exc:
        _log.exception("Stripe API error during checkout session creation: %s", exc)
        raise error_response(502, "Payment provider error")
    except Exception as exc:
        _log.exception("Unexpected error during checkout session creation")
        raise error_response(500, "Failed to create checkout session")


# ---------------------------------------------------------------------------
# POST /billing/portal-session
# ---------------------------------------------------------------------------


@router.post("/portal-session", summary="Create billing portal session")
async def create_portal_session(
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(10, scope="billing")),
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
        session = await asyncio.to_thread(
            stripe_mod.billing_portal.Session.create,
            customer=sub["stripe_customer_id"],
            return_url="collectai://settings",
        )
        return JSONResponse({"url": session.url})
    except stripe_mod.error.StripeError as exc:
        _log.exception("Stripe API error during portal session creation: %s", exc)
        raise error_response(502, "Payment provider error")
    except Exception as exc:
        _log.exception("Unexpected error during portal session creation")
        raise error_response(500, "Failed to create portal session")


# ---------------------------------------------------------------------------
# POST /billing/web/checkout-session  (web-only hybrid subscription)
# ---------------------------------------------------------------------------
# Web subscribers pay via Stripe directly (no Apple cut). The iOS app reads
# the same `subscriptions` table — a row with status='active' unlocks Pro
# regardless of whether the purchase came from IAP or web. Apple's Guideline
# 3.1.3 allows the unlock; we just cannot promote this URL inside the iOS app.
# See docs/HYBRID_WEB_SUBSCRIPTION_PLAN.md.

@router.post("/web/checkout-session", summary="Create web Stripe checkout session")
async def create_web_checkout_session(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(10, scope="billing_web")),
):
    """Create a Stripe Checkout session for the WEB pricing tier (5% off iOS)."""
    stripe_mod = _get_stripe()
    if not stripe_mod or not STRIPE_SECRET_KEY:
        raise error_response(503, "Billing not configured")
    if not DB_ENABLED:
        raise error_response(503, "Database not available")

    body = await request.json()
    interval = (body.get("interval") or "monthly").lower()
    if interval not in ("monthly", "yearly"):
        raise error_response(400, "interval must be 'monthly' or 'yearly'")

    price_id = STRIPE_PRICE_PRO_MONTHLY_WEB if interval == "monthly" else STRIPE_PRICE_PRO_YEARLY_WEB
    if not price_id:
        raise error_response(
            503,
            f"Web Stripe Price ID not configured for pro/{interval}. "
            f"Set STRIPE_PRICE_PRO_{'MONTHLY' if interval == 'monthly' else 'YEARLY'}_WEB.",
        )

    # Block duplicate checkout if user already has active Pro
    existing = await _get_subscription(user_id)
    if existing and existing.get("status") in ("active", "trialing"):
        raise error_response(409, "You are already subscribed")

    try:
        customer_id = await _get_or_create_stripe_customer(user_id, stripe_mod)
        session = await asyncio.to_thread(
            stripe_mod.checkout.Session.create,
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="https://sparrowcollect.com/pro/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://sparrowcollect.com/pro/cancel",
            allow_promotion_codes=True,
            metadata={"user_id": user_id, "plan": "pro", "source": "web"},
            subscription_data={"metadata": {"user_id": user_id, "source": "web"}},
        )
        return JSONResponse({"url": session.url, "session_id": session.id})
    except stripe_mod.error.StripeError as exc:
        _log.exception("Stripe API error during web checkout: %s", exc)
        raise error_response(502, "Payment provider error")
    except Exception:
        _log.exception("Unexpected error during web checkout session creation")
        raise error_response(500, "Failed to create checkout session")


# ---------------------------------------------------------------------------
# GET /billing/status
# ---------------------------------------------------------------------------


@router.get("/status", summary="Get subscription status")
async def get_billing_status(
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(30, scope="billing")),
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

    # current_period_end comes back from asyncpg as a datetime; FastAPI's
    # default JSONResponse encoder doesn't know how to serialize that and
    # 500s with `Object of type datetime is not JSON serializable`.
    # Pre-2026-05-02 this was masked because the only existing
    # subscription row had period_end IS NULL, but as soon as a paid
    # user appeared the entire FE billing flow broke. Coerce to ISO-8601
    # string here and let the FE parse if needed.
    # isinstance, not hasattr: duck-typing a conversion is what shipped every
    # search price as a string (see app/lib/json_safe.py). Harmless here today —
    # no float has .isoformat — but it is the shape that gets copy-pasted.
    period_end = json_safe_value(sub.get("current_period_end"))

    return JSONResponse({
        "plan": plan,
        "status": sub.get("status", "active"),
        "current_period_end": period_end,
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "limits": limits,
    })


# ---------------------------------------------------------------------------
# POST /billing/webhook
# ---------------------------------------------------------------------------


@router.post("/webhook", summary="Handle Stripe webhook")
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
        _log.warning("Invalid Stripe webhook payload (malformed JSON)")
        return JSONResponse({"error": "Invalid payload"}, status_code=400)
    except stripe_mod.error.SignatureVerificationError as exc:
        _log.warning("Stripe webhook signature verification failed: %s", exc)
        return JSONResponse({"error": "Invalid signature"}, status_code=400)
    except stripe_mod.error.StripeError as exc:
        _log.exception("Stripe error during webhook event construction: %s", exc)
        return JSONResponse({"error": "Webhook processing error"}, status_code=400)

    # Stripe SDK 15.x returns StripeObject from construct_event; .get()
    # is missing on Mapping subclasses. Convert the whole event tree to
    # plain dicts so every downstream .get(...) call works without
    # `AttributeError: get`. Replaces the per-handler conversion that
    # was done below — once at the entry is cleaner. See incident
    # 2026-05-02 — webhook 500'd on subscription.updated/deleted before.
    if hasattr(event, "to_dict_recursive"):
        event = event.to_dict_recursive()
    elif hasattr(event, "to_dict"):
        event = event.to_dict()

    event_id = event.get("id", "")
    event_type = event["type"]

    pool = get_pool()

    if await _event_already_processed(event_id, event_type, pool):
        _log.info("Stripe webhook duplicate skipped: %s", event_id)
        return JSONResponse({"received": True, "duplicate": True})

    data = event["data"]["object"]
    _log.info("Stripe webhook: %s (id=%s)", event_type, event_id)

    if pool is None:
        _log.warning("Stripe webhook received but DB is not available")
        return JSONResponse({"received": True})

    if event_type == "checkout.session.completed":
        metadata_type = data.get("metadata", {}).get("type", "")
        if metadata_type == "event_sponsor":
            await _handle_sponsor_checkout_completed(pool, data)
        elif metadata_type == "sponsor_subscription":
            await _handle_sponsor_subscription_completed(pool, data)
        elif metadata_type == "event_ticket":
            await _handle_ticket_checkout_completed(pool, data)
        else:
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
    # Demand signal so subscription cohorts join with other demand data
    # without needing a Stripe API roundtrip every time.
    try:
        from app.features.data_moat import record_demand_signal
        await record_demand_signal(
            signal_type="subscription_purchased",
            item_key=plan,
            user_id=user_id,
        )
    except Exception:
        pass


async def _handle_subscription_updated(pool: Any, subscription: dict):
    """Subscription updated (plan change, renewal, etc.)."""
    sub_id = subscription.get("id")
    status = subscription.get("status", "active")
    cancel_at_period_end = subscription.get("cancel_at_period_end", False)
    current_period_start = subscription.get("current_period_start")
    current_period_end = subscription.get("current_period_end")

    period_start = _safe_timestamp(current_period_start)
    period_end = _safe_timestamp(current_period_end)

    # Check if this is a sponsor subscription first
    try:
        sponsor_row = await pool.fetchrow(
            "SELECT id FROM sponsor_subscriptions WHERE stripe_subscription_id = $1",
            sub_id,
        )
        if sponsor_row:
            await pool.execute(
                """
                UPDATE sponsor_subscriptions SET
                    status = $1, current_period_end = $2, updated_at = now()
                WHERE stripe_subscription_id = $3
                """,
                status, period_end, sub_id,
            )
            _log.info("Sponsor subscription %s updated: status=%s", sub_id, status)
            return
    except Exception:
        pass  # Table may not exist yet — fall through to user subscriptions

    # Map Stripe price to plan using centralized reverse lookup
    items = subscription.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = _PRICE_TO_PLAN.get(price_id, "free") if price_id else "free"
    if plan == "free" and price_id:
        _log.warning("Unrecognised Stripe price_id '%s' — defaulting to free plan", price_id)

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

    # Check if this is a sponsor subscription first
    try:
        sponsor_row = await pool.fetchrow(
            "SELECT id FROM sponsor_subscriptions WHERE stripe_subscription_id = $1",
            sub_id,
        )
        if sponsor_row:
            await pool.execute(
                "UPDATE sponsor_subscriptions SET status = 'canceled', updated_at = now() "
                "WHERE stripe_subscription_id = $1",
                sub_id,
            )
            _log.info("Sponsor subscription %s deleted — canceled", sub_id)
            return
    except Exception:
        pass  # Table may not exist yet

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


async def _handle_sponsor_checkout_completed(pool: Any, session: dict):
    """After successful sponsor checkout, activate event sponsorship."""
    metadata = session.get("metadata", {})
    event_id = metadata.get("event_id")
    tier = metadata.get("tier", "featured")
    sponsor_name = metadata.get("sponsor_name", "")
    user_id = metadata.get("user_id")

    if not event_id:
        _log.warning("sponsor checkout.session.completed missing event_id in metadata")
        return

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)

    # Use a transaction to ensure atomicity of sponsorship activation + analytics
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Activate sponsorship on the event
            await conn.execute(
                """
                UPDATE events SET
                    is_sponsored = true,
                    sponsor_name = $2,
                    sponsor_tier = $3,
                    sponsor_paid_at = $4,
                    sponsor_expires_at = $5,
                    updated_at = $4
                WHERE id = $1
                """,
                event_id, sponsor_name, tier, now, expires_at,
            )

            # Create analytics row
            await conn.execute(
                """
                INSERT INTO event_sponsor_analytics (event_id)
                VALUES ($1)
                ON CONFLICT (event_id) DO NOTHING
                """,
                event_id,
            )

    _log.info("Event %s sponsored: tier=%s, sponsor=%s, expires=%s", event_id, tier, sponsor_name, expires_at)

    # For promoted/spotlight tiers: send push notifications to category followers
    # (outside the transaction — push failures should not roll back sponsorship)
    if tier in ("promoted", "spotlight"):
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT title, category_id FROM events WHERE id = $1", event_id
                )
                if row and row["category_id"]:
                    # Fixed 2026-07-24. This used to JOIN `device_tokens`, a
                    # table with zero writers anywhere (0 rows) — the real one
                    # is `user_push_tokens`, and the column differs too
                    # (`token` vs `push_token`). Every sponsored-event blast
                    # therefore reached nobody, silently, because the whole
                    # block is wrapped in the except below.
                    #
                    # Do NOT reintroduce a direct join here: user_category_
                    # follows.user_id is `uuid` while user_push_tokens.user_id
                    # is `text`, so joining them raises
                    # "operator does not exist: text = uuid" — which this same
                    # except would have swallowed again. Select the followers,
                    # then let send_push_to_user do the token lookup; it owns
                    # that query and also persists to notification_history, so
                    # the blast now shows up in the in-app inbox too.
                    follower_rows = await conn.fetch(
                        "SELECT DISTINCT user_id FROM user_category_follows WHERE category_id = $1",
                        row["category_id"],
                    )
                    from app.push import send_push_to_user
                    title = row["title"] or "Sponsored Event"
                    sent = 0
                    for fr in follower_rows:
                        sent += await send_push_to_user(
                            conn,
                            str(fr["user_id"]),
                            f"New {tier.title()} Event",
                            f"{sponsor_name} presents: {title}",
                            data={"event_id": event_id, "type": "sponsored_event"},
                            notification_type="sponsored_event",
                            deep_link=f"/events/{event_id}",
                        )
                    # A paid tier delivering 0 pushes is a billing-visible
                    # failure, not routine info — say so loudly enough to be
                    # greppable. This is exactly the state that hid for months.
                    if follower_rows and sent == 0:
                        _log.error(
                            "Sponsor push for event %s reached 0 devices: %d category followers, "
                            "none with an active push token",
                            event_id, len(follower_rows),
                        )
                    elif not follower_rows:
                        _log.warning(
                            "Sponsor push for event %s: no followers for category %s",
                            event_id, row["category_id"],
                        )
                    else:
                        _log.info(
                            "Sent %d sponsor pushes to %d category followers for event %s",
                            sent, len(follower_rows), event_id,
                        )
        except Exception as push_err:
            # Keep the sponsorship transaction intact, but do not let a paid
            # feature fail at WARNING level — this swallowed the bug above.
            _log.error(
                "Failed to send sponsor push notifications for event %s: %s",
                event_id, push_err, exc_info=True,
            )


async def _handle_sponsor_subscription_completed(pool: Any, session: dict):
    """After successful sponsor subscription checkout, record subscription."""
    metadata = session.get("metadata", {})
    company_id = metadata.get("company_id")
    tier = metadata.get("tier", "featured")
    user_id = metadata.get("user_id")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not company_id or not user_id:
        _log.warning("sponsor_subscription checkout missing company_id/user_id in metadata")
        return

    # Ensure table exists
    try:
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS sponsor_subscriptions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                company_id UUID NOT NULL,
                user_id UUID NOT NULL,
                stripe_customer_id VARCHAR(255),
                stripe_subscription_id VARCHAR(255),
                tier VARCHAR(50) NOT NULL DEFAULT 'featured',
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                current_period_end TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(company_id)
            )
        """)
    except Exception:
        pass

    await pool.execute(
        """
        INSERT INTO sponsor_subscriptions
            (company_id, user_id, stripe_customer_id, stripe_subscription_id, tier, status)
        VALUES ($1, $2, $3, $4, $5, 'active')
        ON CONFLICT (company_id) DO UPDATE SET
            stripe_customer_id = $3,
            stripe_subscription_id = $4,
            tier = $5,
            status = 'active',
            updated_at = now()
        """,
        company_id, user_id, customer_id, subscription_id, tier,
    )
    _log.info("Sponsor subscription created: company=%s tier=%s sub=%s", company_id, tier, subscription_id)


async def _handle_ticket_checkout_completed(pool: Any, session: dict):
    """After successful event ticket purchase, record ticket and RSVP user."""
    metadata = session.get("metadata", {})
    event_id = metadata.get("event_id")
    user_id = metadata.get("user_id")
    stripe_session_id = session.get("id", "")
    amount = session.get("amount_total", 0)

    if not event_id or not user_id:
        _log.warning("event_ticket checkout missing event_id/user_id in metadata")
        return

    fee_cents = int(amount * 0.05) if amount else 0

    # Ensure event_tickets table exists
    try:
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS event_tickets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                event_id UUID NOT NULL,
                user_id UUID NOT NULL,
                stripe_session_id VARCHAR(255),
                amount_cents INTEGER NOT NULL,
                fee_cents INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(50) NOT NULL DEFAULT 'paid',
                created_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(event_id, user_id)
            )
        """)
    except Exception:
        pass

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Record ticket
            await conn.execute(
                """
                INSERT INTO event_tickets (event_id, user_id, stripe_session_id, amount_cents, fee_cents)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (event_id, user_id) DO UPDATE SET
                    status = 'paid', stripe_session_id = $3, amount_cents = $4, fee_cents = $5
                """,
                event_id, user_id, stripe_session_id, amount or 0, fee_cents,
            )

            # RSVP as going
            await conn.execute(
                """
                INSERT INTO event_attendees (event_id, user_id, status)
                VALUES ($1, $2, 'going')
                ON CONFLICT (event_id, user_id) DO UPDATE SET status = 'going'
                """,
                event_id, user_id,
            )

    _log.info("Ticket purchased: event=%s user=%s amount=%s fee=%s", event_id, user_id, amount, fee_cents)


# ---------------------------------------------------------------------------
# POST /billing/revenuecat-webhook
# ---------------------------------------------------------------------------
# Mobile Pro/Premium purchases go through RevenueCat/StoreKit, not Stripe. Until
# this existed, subscriptions held zero paid rows and mobile revenue was
# invisible server-side — no creator payout could be computed from anything
# queryable. This writes both the current-state row (subscriptions) and the
# append-only ledger (subscription_events) that payouts are summed from.
#
# NOTE: RevenueCat's payload field names are read defensively below (COALESCE
# across the documented aliases) because they differ by event type and API
# version. Verify against a real sample payload in the RevenueCat dashboard
# (Integrations -> Webhooks -> Send test event) before trusting the amounts.

def _rc_identified_user_id(app_user_id: str | None) -> str | None:
    """Return `app_user_id` only when it is something `::uuid` will accept.

    `subscription_events.user_id` and `subscriptions.user_id` are UUID columns
    and the handler binds with `$n::uuid`, so a non-UUID value does not degrade
    — it raises `invalid input syntax for type uuid` and takes the whole insert
    with it.

    Live on 2026-08-30: the moment RevenueCat's Events filter was corrected and
    it started delivering, every POST returned 500 with
    `revenuecat: ledger insert failed`, because a TEST event's app_user_id is
    literally `test_app_user_id`. The handler already dropped `$RCAnonymousID:`
    ids for the same reason; it just did not generalise.

    Dropping to NULL is not data loss: `app_user_id` is a TEXT column that
    stores whatever RevenueCat sent, so the ledger still records the event and
    the payout it represents. Only the FK-shaped join is skipped, which is
    correct — we genuinely cannot identify that user.

    A real member's id IS a uuid (AuthProvider calls Purchases.logIn with the
    Supabase uid), so this guard changes nothing for real traffic. It stops the
    500s that make RevenueCat retry and eventually disable the webhook.
    """
    if not app_user_id:
        return None
    candidate = str(app_user_id)
    # Kept for readability, though the UUID check below already subsumes it —
    # `$RCAnonymousID:...` is not parseable as a UUID either. Mutation-testing
    # proved that: deleting this branch leaves every test green. It stays as a
    # named statement of a real RevenueCat concept, NOT as a load-bearing
    # guard, and removing it would not change behaviour.
    if candidate.startswith("$RCAnonymousID"):
        return None
    try:
        uuid.UUID(candidate)
    except (ValueError, AttributeError, TypeError):
        return None
    return candidate


def _rc_exc_detail(exc: BaseException) -> str:
    """One-line "why" for a webhook failure, safe to interpolate into a log.

    On 2026-08-30 the handler logged `ledger insert failed for <id>` and
    nothing else on that line. The traceback existed in bake.log, but on lines
    that do not contain "revenuecat" — so every grep scoped to the integration
    missed it, and two wrong hypotheses were formed while the real cause (an FK
    violation naming the offending key) sat unread.

    asyncpg's `detail` is the part that matters: it carried
    `Key (user_id)=(2b7db244-…) is not present in table "users"`, which is the
    sentence that identified the bug. `constraint_name` says which rule broke.

    Newlines are collapsed so one failure is one grep-able line, and every
    attribute read is defensive — a logger that throws while reporting a
    failure turns a diagnosable error into a silent one.
    """
    parts = [type(exc).__name__]
    try:
        msg = str(exc).strip()
        if msg:
            parts.append(msg)
    except Exception:  # pragma: no cover - str() on a hostile exception
        pass
    for attr in ("constraint_name", "detail"):
        try:
            val = getattr(exc, attr, None)
        except Exception:  # pragma: no cover
            val = None
        if val:
            parts.append(f"{attr}={val}")
    return " | ".join(" ".join(str(p).split()) for p in parts)


async def _rc_resolve_user_id(app_user_id: str | None, pool) -> str | None:
    """The id, only if it is a UUID *and* a real row in `auth.users`.

    `_rc_identified_user_id` proves the FORMAT. This proves EXISTENCE, and the
    two are different failures a day apart:

      2026-08-30 13:35  invalid input syntax for type uuid: "test_app_user_id"
      2026-08-30 14:26  violates foreign key constraint
                        subscription_events_user_id_fkey
                        Key (user_id)=(2b7db244-…) is not present in "users"

    RevenueCat's test events invent a random UUID. It passes the format check
    and then fails the FK, and both `subscription_events.user_id` and
    `subscriptions.user_id` reference `auth.users(id)`.

    NULL is the designed state for this: the events FK is ON DELETE SET NULL,
    so the schema already says an event may outlive or precede its user. The
    ledger still records the event and its payout via the `app_user_id` TEXT
    column; only the identified-user join is skipped.

    Returns None without querying when the format is already wrong, and None
    when there is no pool — absent a database we cannot prove the user exists,
    and claiming it is what raises 500s that make RevenueCat retry and
    eventually disable the webhook.
    """
    candidate = _rc_identified_user_id(app_user_id)
    if not candidate or pool is None:
        return None
    try:
        exists = await pool.fetchval(
            "SELECT 1 FROM auth.users WHERE id = $1::uuid", candidate
        )
    except Exception as exc:
        _log.warning("revenuecat: could not verify user %s: %s", candidate, exc)
        return None
    if not exists:
        _log.info(
            "revenuecat: app_user_id %s is a well-formed uuid but not a known "
            "user — recording the event unidentified", candidate,
        )
        return None
    return candidate



@router.post("/revenuecat-webhook", summary="Handle RevenueCat webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: str = Header(None, alias="Authorization"),
):
    """Handle RevenueCat webhook events (no user auth — shared-secret header)."""
    if not REVENUECAT_WEBHOOK_AUTH:
        # Never accept unauthenticated revenue writes.
        raise error_response(503, "RevenueCat webhook not configured")

    # compare_digest avoids leaking the secret through timing.
    if not authorization or not hmac.compare_digest(authorization, REVENUECAT_WEBHOOK_AUTH):
        _log.warning("revenuecat: rejected webhook with bad Authorization header")
        raise error_response(401, "Invalid webhook signature")

    try:
        body = await request.json()
    except Exception:
        raise error_response(400, "Malformed JSON body")

    event = body.get("event") or {}
    event_id = event.get("id")
    event_type = event.get("type")
    if not event_id or not event_type:
        raise error_response(400, "Missing event id or type")

    pool = await get_pool() if DB_ENABLED else None
    if pool is None:
        # 503 (not 200) so RevenueCat retries rather than dropping the event.
        raise error_response(503, "Database unavailable")

    if await _event_already_processed(event_id, f"revenuecat.{event_type}", pool):
        _log.info("revenuecat: duplicate event %s (%s) ignored", event_id, event_type)
        return JSONResponse({"ok": True, "duplicate": True})

    app_user_id = event.get("app_user_id")
    plan = _rc_plan_from_event(event)
    revenue_cents = _rc_revenue_cents(event)
    affiliate_code = _rc_affiliate_code(event)
    occurred_at = _rc_ms_to_dt(event.get("purchased_at_ms")) or datetime.now(timezone.utc)
    expires_at = _rc_ms_to_dt(event.get("expiration_at_ms"))

    # app_user_id is our auth.users.id (purchases.ts calls Purchases.logIn).
    # Anonymous RevenueCat ids ($RCAnonymousID:...) cannot be attributed.
    user_id = await _rc_resolve_user_id(app_user_id, pool)

    # Fall back to the profile's stored code when the subscriber attribute is
    # missing — e.g. a user who upgraded from a build predating setAttributes.
    if affiliate_code is None and user_id:
        try:
            affiliate_code = await pool.fetchval(
                "SELECT referred_by_code FROM profiles WHERE id = $1::uuid", user_id
            )
        except Exception as exc:
            _log.warning("revenuecat: profile lookup failed for %s: %s", user_id, exc)

    # Ledger row first: it is the payout source of truth, and its UNIQUE
    # event_id is what makes a retry safe.
    try:
        await pool.execute(
            """
            INSERT INTO subscription_events (
                event_id, event_type, provider, user_id, app_user_id, product_id,
                plan, store, environment, revenue_cents, currency,
                takehome_percentage, affiliate_code, occurred_at, raw
            )
            VALUES ($1, $2, 'revenuecat', $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb)
            ON CONFLICT (event_id) DO NOTHING
            """,
            event_id, event_type, user_id, app_user_id, event.get("product_id"),
            plan, event.get("store"), event.get("environment"), revenue_cents,
            event.get("currency"), event.get("takehome_percentage"),
            affiliate_code, occurred_at, json.dumps(event),
        )
    except Exception as exc:
        # 500 so RevenueCat retries — losing a revenue event loses a payout.
        _log.exception(
            "revenuecat: ledger insert failed for %s — %s",
            event_id, _rc_exc_detail(exc),
        )
        raise error_response(500, "Failed to record subscription event") from exc

    # Current-state row. Only for identified users on entitlement-changing events.
    if user_id and event_type in (_RC_ACTIVE_EVENTS | _RC_ENDED_EVENTS):
        is_active = event_type in _RC_ACTIVE_EVENTS
        status = "active" if is_active else ("paused" if event_type == "SUBSCRIPTION_PAUSED" else "expired")
        try:
            await pool.execute(
                """
                INSERT INTO subscriptions (
                    user_id, provider, revenuecat_app_user_id, revenuecat_product_id,
                    plan, status, current_period_end
                )
                VALUES ($1::uuid, 'revenuecat', $2, $3, $4, $5, $6)
                ON CONFLICT (user_id) DO UPDATE SET
                    provider = 'revenuecat',
                    revenuecat_app_user_id = EXCLUDED.revenuecat_app_user_id,
                    revenuecat_product_id = EXCLUDED.revenuecat_product_id,
                    plan = EXCLUDED.plan,
                    status = EXCLUDED.status,
                    current_period_end = EXCLUDED.current_period_end,
                    updated_at = now()
                """,
                user_id, app_user_id, event.get("product_id"),
                plan if is_active else "free", status, expires_at,
            )
        except Exception as sub_exc:
            # `as sub_exc`, and NOT reusing `exc` from the ledger block above:
            # Python deletes an except-clause name when that block ends, so
            # referencing it here raises NameError — a crash while REPORTING a
            # failure, which converts a diagnosable error into a silent one.
            #
            # The ledger already landed, so revenue is not lost. Log loudly and
            # return 200 — a retry would be a no-op on the ledger anyway.
            _log.exception(
                "revenuecat: subscriptions upsert failed for user %s — %s",
                user_id, _rc_exc_detail(sub_exc),
            )

    _log.info(
        "revenuecat: %s user=%s plan=%s revenue=%s%s code=%s",
        event_type, user_id, plan, revenue_cents, event.get("currency") or "", affiliate_code,
    )
    return JSONResponse({"ok": True})
