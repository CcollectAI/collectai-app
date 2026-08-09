"""
RevenueCat webhook payload parsing.

Kept free of FastAPI/DB imports so the mapping logic can be exercised directly
by tests and by the creator-dashboard E2E, without standing up the app. The
route in billing_router.py is the only caller in production.

NOTE: RevenueCat's field names vary by event type and API version. These read
defensively across the documented aliases. Verify against a real payload
(RevenueCat dashboard -> Integrations -> Webhooks -> Send test event) before
trusting the amounts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger("collectai.billing")


# RevenueCat event types that represent the user holding an active entitlement.
_RC_ACTIVE_EVENTS = {
    "INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION",
    "NON_RENEWING_PURCHASE", "PRODUCT_CHANGE", "TRANSFER",
}
# Types that end it. CANCELLATION is deliberately absent: it means "will not
# renew", and the user keeps access until expiration.
_RC_ENDED_EVENTS = {"EXPIRATION", "SUBSCRIPTION_PAUSED"}
# Only these move money. CANCELLATION/EXPIRATION carry a price field on some
# API versions, and counting them would inflate a creator's payout.
_RC_REVENUE_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "NON_RENEWING_PURCHASE", "PRODUCT_CHANGE"}


def _rc_plan_from_event(event: dict) -> str:
    """Map RevenueCat entitlement ids to our plan tiers (see purchases.ts)."""
    entitlements = event.get("entitlement_ids") or []
    if not entitlements and event.get("entitlement_id"):
        entitlements = [event["entitlement_id"]]
    if "premium" in entitlements:
        return "premium"
    if "pro" in entitlements:
        return "pro"
    return "free"


def _rc_revenue_cents(event: dict) -> int:
    """Gross revenue in minor units, or 0 for non-revenue events."""
    if event.get("type") not in _RC_REVENUE_EVENTS:
        return 0
    price = event.get("price_in_purchased_currency")
    if price is None:
        price = event.get("price")
    if price is None:
        return 0
    try:
        return int(round(float(price) * 100))
    except (TypeError, ValueError):
        _log.warning("revenuecat: unparseable price %r on event %s", price, event.get("id"))
        return 0


def _rc_affiliate_code(event: dict) -> str | None:
    """Creator code, stamped client-side via Purchases.setAttributes()."""
    attrs = event.get("subscriber_attributes") or {}
    entry = attrs.get("affiliate_code")
    # Subscriber attributes arrive as {"affiliate_code": {"value": "LUNA10", ...}}
    if isinstance(entry, dict):
        value = entry.get("value")
    else:
        value = entry
    if not value or not str(value).strip():
        return None
    return str(value).strip().upper()


def _rc_ms_to_dt(ms: Any) -> datetime | None:
    if ms in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
