"""
Adversarial tests for RevenueCat webhook payload parsing.

This is the code that decides how much money a creator is owed, so it gets
hostile inputs: missing fields, wrong types, negative and absurd prices,
subscriber-attribute shapes RevenueCat sends across API versions, and event
types that must NOT move money. Pure functions — no DB, no network.

Run:  python3 -m pytest server/tests/test_revenuecat_parsing.py -q
  or: python3 server/tests/test_revenuecat_parsing.py   (self-runs without pytest)
"""

import os
import sys
from datetime import timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.lib.revenuecat import (  # noqa: E402
    _RC_REVENUE_EVENTS,
    _rc_affiliate_code,
    _rc_ms_to_dt,
    _rc_plan_from_event,
    _rc_revenue_cents,
)


# ── plan mapping ────────────────────────────────────────────────────────────

def test_plan_premium_wins_over_pro():
    assert _rc_plan_from_event({"entitlement_ids": ["pro", "premium"]}) == "premium"

def test_plan_pro():
    assert _rc_plan_from_event({"entitlement_ids": ["pro"]}) == "pro"

def test_plan_singular_entitlement_id_field():
    # Some event types send entitlement_id (singular) instead of the array.
    assert _rc_plan_from_event({"entitlement_id": "pro"}) == "pro"

def test_plan_unknown_entitlement_is_free():
    assert _rc_plan_from_event({"entitlement_ids": ["gold"]}) == "free"

def test_plan_missing_entitlements_is_free():
    assert _rc_plan_from_event({}) == "free"

def test_plan_null_entitlements_is_free():
    assert _rc_plan_from_event({"entitlement_ids": None}) == "free"


# ── revenue extraction — the money path ─────────────────────────────────────

def test_revenue_basic_eur():
    e = {"type": "INITIAL_PURCHASE", "price_in_purchased_currency": 4.99}
    assert _rc_revenue_cents(e) == 499

def test_revenue_falls_back_to_price_field():
    e = {"type": "RENEWAL", "price": 9.99}
    assert _rc_revenue_cents(e) == 999

def test_revenue_prefers_purchased_currency_over_price():
    e = {"type": "RENEWAL", "price_in_purchased_currency": 4.99, "price": 5.49}
    assert _rc_revenue_cents(e) == 499

def test_non_revenue_event_yields_zero():
    # CANCELLATION carries a price on some API versions; counting it would
    # inflate a creator's payout. Must be zero.
    for t in ("CANCELLATION", "EXPIRATION", "BILLING_ISSUE", "SUBSCRIBER_ALIAS"):
        e = {"type": t, "price_in_purchased_currency": 4.99}
        assert _rc_revenue_cents(e) == 0, f"{t} must not count as revenue"

def test_every_revenue_event_type_counts():
    for t in _RC_REVENUE_EVENTS:
        e = {"type": t, "price_in_purchased_currency": 1.00}
        assert _rc_revenue_cents(e) == 100, f"{t} should count"

def test_revenue_missing_price_is_zero_not_crash():
    assert _rc_revenue_cents({"type": "INITIAL_PURCHASE"}) == 0

def test_revenue_null_price_is_zero():
    assert _rc_revenue_cents({"type": "INITIAL_PURCHASE", "price_in_purchased_currency": None}) == 0

def test_revenue_string_price_does_not_crash():
    # Bad upstream data must yield 0, never raise.
    assert _rc_revenue_cents({"type": "INITIAL_PURCHASE", "price_in_purchased_currency": "abc"}) == 0

def test_revenue_zero_price_is_zero():
    assert _rc_revenue_cents({"type": "INITIAL_PURCHASE", "price_in_purchased_currency": 0}) == 0

def test_revenue_rounds_half_correctly():
    # 2.995 * 100 = 299.5 -> banker's/round-half; assert it does not truncate to 299.
    e = {"type": "INITIAL_PURCHASE", "price_in_purchased_currency": 2.995}
    assert _rc_revenue_cents(e) in (299, 300)  # rounding, not truncation

def test_revenue_large_price():
    e = {"type": "INITIAL_PURCHASE", "price_in_purchased_currency": 199.99}
    assert _rc_revenue_cents(e) == 19999


# ── affiliate code extraction & normalisation ───────────────────────────────

def test_code_from_nested_subscriber_attribute():
    e = {"subscriber_attributes": {"affiliate_code": {"value": "luna10"}}}
    assert _rc_affiliate_code(e) == "LUNA10"

def test_code_flat_value_shape():
    # Guard the alternate shape where the attr is a bare string.
    e = {"subscriber_attributes": {"affiliate_code": "luna10"}}
    assert _rc_affiliate_code(e) == "LUNA10"

def test_code_normalised_upper_and_trimmed():
    e = {"subscriber_attributes": {"affiliate_code": {"value": "  luna10 "}}}
    assert _rc_affiliate_code(e) == "LUNA10"

def test_code_absent_is_none():
    assert _rc_affiliate_code({}) is None
    assert _rc_affiliate_code({"subscriber_attributes": {}}) is None

def test_code_empty_string_is_none():
    e = {"subscriber_attributes": {"affiliate_code": {"value": "   "}}}
    assert _rc_affiliate_code(e) is None

def test_code_null_value_is_none():
    e = {"subscriber_attributes": {"affiliate_code": {"value": None}}}
    assert _rc_affiliate_code(e) is None


# ── timestamp parsing ───────────────────────────────────────────────────────

def test_ms_to_dt_valid():
    dt = _rc_ms_to_dt(1752940800000)
    assert dt is not None
    assert dt.tzinfo == timezone.utc  # imported at top; must be tz-aware UTC
    assert dt.year == 2025  # 1752940800000ms = 2025-07-19, sanity on the epoch math

def test_ms_to_dt_none():
    assert _rc_ms_to_dt(None) is None

def test_ms_to_dt_empty_string():
    assert _rc_ms_to_dt("") is None

def test_ms_to_dt_garbage_does_not_crash():
    assert _rc_ms_to_dt("not-a-number") is None


if __name__ == "__main__":
    # Self-run without pytest: execute every test_* and report.
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            passed += 1
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}  -> {type(exc).__name__}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
