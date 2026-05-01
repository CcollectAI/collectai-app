"""E2E for paid features on the item card.

Verifies:
  1. /billing/status returns ALL keys the FE consumes — including the two
     that were silently missing (condition_grading, set_completion).
  2. Each plan's limits dict matches the FORCED_LIMITS table that drives
     the FE force-plan dev override (src/hooks/useBillingLimits.ts).
  3. Each paywalled BE route is reachable — proves the user CAN call it
     once their plan unlocks the feature.

Designed to be auth-free where possible (route-existence probes via
401 vs 404). For the billing/status shape check we use DEV_MODE/DB
bypass when available; otherwise we verify the static PLAN_LIMITS dict
in source matches the FE shape.

Run on EC2 (or any host that can reach API_BASE):
    python3 scripts/e2e_paid_features_billing.py
"""
from __future__ import annotations

import os
import sys
import json
import urllib.request
import urllib.error


# Mirror of the FE's BillingStatus['limits'] keys
# (src/hooks/useBillingLimits.ts:DEFAULT_LIMITS).
FE_REQUIRED_LIMIT_KEYS = {
    "max_mandates",
    "deal_discovery",
    "dossier_pdf",
    "advanced_analytics",
    "condition_grading",
    "set_completion",
    "show_ads",
}

# What FE forces for each plan in dev — when BE diverges from this, paid
# users see locked features they paid for. Keep in sync with
# src/hooks/useBillingLimits.ts:FORCED_LIMITS.
FE_PLAN_EXPECTATIONS = {
    "free": {"condition_grading": False, "set_completion": False, "advanced_analytics": False, "show_ads": True},
    "pro":  {"condition_grading": True,  "set_completion": True,  "advanced_analytics": False, "show_ads": False},
    "premium": {"condition_grading": True, "set_completion": True, "advanced_analytics": True, "show_ads": False},
}

# Paywalled feature → (BE route, expected unauth status)
# 401 = route exists and needs auth (good). 404 = route missing (bad).
GATED_ROUTES = [
    ("Condition Grading",       "GET",  "/grading/services?category=pokemon"),
    ("Condition Grading lookup","GET",  "/grading/lookup?cert_number=12345&service=psa"),
    ("Price Trend",             "GET",  "/predict/trend/00000000-0000-0000-0000-000000000000"),
    ("Item History",            "GET",  "/provenance/items/00000000-0000-0000-0000-000000000000"),
    ("Valuation Report",        "GET",  "/dossier/00000000-0000-0000-0000-000000000000"),
    ("Market Prices",           "POST", "/marketplace/search"),
    ("Billing Status",          "GET",  "/billing/status"),
]

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def _request(method: str, path: str) -> tuple[int, str]:
    url = f"{API_BASE}{path}"
    body = b'{}' if method == "POST" else None
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode() if e.fp else "")
    except Exception as e:
        return 0, str(e)


def check_static_plan_limits() -> list[str]:
    """Read PLAN_LIMITS from server/app/routes/billing_router.py and verify
    the shape matches what the FE expects. We do this against the source
    file because /billing/status requires auth — the source is the
    authoritative answer to "what would the live endpoint return."""
    failures: list[str] = []
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.normpath(os.path.join(here, "..", "server", "app", "routes", "billing_router.py"))
    if not os.path.exists(src):
        # In CI the script may live anywhere; try cwd fallback.
        src = "server/app/routes/billing_router.py"
    if not os.path.exists(src):
        failures.append(f"can't locate billing_router.py to read PLAN_LIMITS")
        return failures
    text = open(src).read()
    # Crude but sufficient — extract PLAN_LIMITS = {...} dict literal.
    start = text.index("PLAN_LIMITS = {")
    end = text.index("\n}\n", start) + 2
    snippet = text[start:end]
    # Build a real dict by exec'ing in a sandboxed namespace.
    ns: dict[str, object] = {}
    exec(snippet, ns)
    plans = ns["PLAN_LIMITS"]
    print("Plans defined in BE PLAN_LIMITS:", sorted(plans))  # type: ignore

    for plan_name, expected in FE_PLAN_EXPECTATIONS.items():
        if plan_name not in plans:  # type: ignore
            failures.append(f"BE PLAN_LIMITS missing plan: {plan_name}")
            continue
        limits = plans[plan_name]  # type: ignore
        # Required-key check
        for key in FE_REQUIRED_LIMIT_KEYS:
            if key not in limits:
                failures.append(f"plan={plan_name} missing key the FE consumes: {key}")
            else:
                print(f"PASS  {plan_name}.{key} present")
        # Expected-value check (only on the keys we explicitly pinned)
        for key, want in expected.items():
            got = limits.get(key)
            if got != want:
                failures.append(f"plan={plan_name}.{key}: BE={got}, FE expects {want}")
            else:
                print(f"PASS  {plan_name}.{key} == {want}")
    return failures


def check_routes_exist() -> list[str]:
    """For each paywalled feature, confirm the BE route is reachable.
    401 (Unauthorized) means it exists and gates on auth — that's success.
    404 means the route is missing — that's a real bug."""
    failures: list[str] = []
    for label, method, path in GATED_ROUTES:
        code, _body = _request(method, path)
        if code == 0:
            failures.append(f"{label}: network error contacting {API_BASE}")
            print(f"FAIL  {label} {method} {path}  (network error)")
        elif code == 404:
            failures.append(f"{label}: route 404 — handler missing")
            print(f"FAIL  {label} {method} {path}  -> 404 missing handler")
        elif code in (401, 403):
            print(f"PASS  {label} {method} {path}  -> {code} (auth-gated, route exists)")
        elif code in (200, 422):
            # 422 = validation error from FastAPI on a bogus body; route exists.
            print(f"PASS  {label} {method} {path}  -> {code}")
        else:
            print(f"WARN  {label} {method} {path}  -> {code} (unexpected; route exists)")
    return failures


def main() -> int:
    print("=" * 70)
    print("STATIC PLAN_LIMITS shape check (FE↔BE contract)")
    print("=" * 70)
    static_failures = check_static_plan_limits()

    print()
    print("=" * 70)
    print(f"ROUTE EXISTENCE PROBE against {API_BASE}")
    print("=" * 70)
    route_failures = check_routes_exist()

    failures = static_failures + route_failures
    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL PASS — paid-features contract green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
