"""
Policy Engine for the Smart Deal Agent.

Pure-logic module — no HTTP, no DB, no side effects.
Validates a candidate marketplace hit against a purchase mandate's constraints
and computes a composite deal score.

Usage:
    verdict = evaluate(mandate, hit, prediction)
    if verdict.passed:
        # persist deal, send notification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PolicyVerdict:
    """Result of evaluating a marketplace hit against a mandate."""
    passed: bool
    reasons: list[str] = field(default_factory=list)
    deal_score: float = 0.0
    price_vs_q50_pct: float = 0.0


def evaluate(
    mandate: Dict[str, Any],
    hit: Dict[str, Any],
    prediction: Optional[Dict[str, Any]] = None,
) -> PolicyVerdict:
    """Validate a candidate marketplace hit against mandate constraints.

    Args:
        mandate: Row from purchase_mandates (dict-like).
        hit: A marketplace hit dict with keys: price, source, provenance_score,
             condition, url, title, etc.
        prediction: Optional price prediction dict with q10, q50, q90 keys.

    Returns:
        PolicyVerdict with pass/fail, human-readable reasons, deal_score,
        and price_vs_q50_pct.
    """
    reasons: list[str] = []
    failed = False

    price = float(hit.get("price", 0) or 0)
    shipping_cost = float(hit.get("shipping_cost", 0) or 0)
    total_cost = price + shipping_cost
    source = str(hit.get("source", ""))
    provenance = float(hit.get("provenance_score", 0) or 0)
    listing_region = hit.get("listing_region")
    is_domestic_only = bool(hit.get("domestic_only", False))

    max_price = float(mandate.get("max_price", 0) or 0)
    max_budget = mandate.get("max_total_budget")
    spent = float(mandate.get("spent_total", 0) or 0)
    min_trust = float(mandate.get("min_trust_score", 0.60) or 0.60)
    cooldown_hours = int(mandate.get("cooldown_hours", 24) or 24)
    allowed_sources = mandate.get("allowed_sources") or []
    expires_at = mandate.get("expires_at")
    last_deal_at = mandate.get("last_deal_at")
    mandate_region = mandate.get("region")

    now = datetime.now(timezone.utc)

    # ── Check 1: Total cost (price + shipping) within max_price ────────────
    if total_cost <= max_price:
        if shipping_cost > 0:
            reasons.append(
                f"total {_fmt_eur(total_cost)} (price {_fmt_eur(price)} + shipping {_fmt_eur(shipping_cost)}) <= max {_fmt_eur(max_price)}"
            )
        else:
            reasons.append(f"price {_fmt_eur(price)} <= max {_fmt_eur(max_price)}")
    else:
        if shipping_cost > 0:
            reasons.append(
                f"FAIL: total {_fmt_eur(total_cost)} (price {_fmt_eur(price)} + shipping {_fmt_eur(shipping_cost)}) > max {_fmt_eur(max_price)}"
            )
        else:
            reasons.append(f"FAIL: price {_fmt_eur(price)} > max {_fmt_eur(max_price)}")
        failed = True

    # ── Check 2: Budget not exceeded (using total cost) ────────────────────
    if max_budget is not None:
        max_budget_f = float(max_budget)
        remaining = max_budget_f - spent
        if spent + total_cost <= max_budget_f:
            reasons.append(f"budget OK: {_fmt_eur(remaining)} remaining")
        else:
            reasons.append(
                f"FAIL: budget exceeded ({_fmt_eur(spent)} + {_fmt_eur(total_cost)} > {_fmt_eur(max_budget_f)})"
            )
            failed = True

    # ── Check 3: Cooldown respected ────────────────────────────────────────
    if last_deal_at is not None:
        if isinstance(last_deal_at, str):
            try:
                last_deal_dt = datetime.fromisoformat(last_deal_at.replace("Z", "+00:00"))
            except ValueError:
                last_deal_dt = None
        elif isinstance(last_deal_at, datetime):
            last_deal_dt = last_deal_at if last_deal_at.tzinfo else last_deal_at.replace(tzinfo=timezone.utc)
        else:
            last_deal_dt = None

        if last_deal_dt is not None:
            elapsed = now - last_deal_dt
            cooldown_td = timedelta(hours=cooldown_hours)
            if elapsed >= cooldown_td:
                hours_ago = elapsed.total_seconds() / 3600
                reasons.append(f"cooldown OK: last deal {hours_ago:.0f}h ago >= {cooldown_hours}h")
            else:
                # D7: this mandate-level blanket cooldown used to FAIL every deal
                # for N hours after ANY single deal — so finding one deal hid all
                # OTHER (different-item) deals for the rest of the window. That's
                # over-suppression. Per-listing cooldown is enforced correctly in
                # the agent (_get_existing_urls + _get_user_recent_deal_urls) and
                # notification rate is capped in the worker, so this is now
                # advisory only and no longer blocks the verdict.
                hours_left = (cooldown_td - elapsed).total_seconds() / 3600
                reasons.append(f"cooldown note: mandate last deal {hours_left:.1f}h ago (per-listing cooldown still applies)")

    # ── Check 4: Trust score ───────────────────────────────────────────────
    if provenance >= min_trust:
        reasons.append(f"provenance {provenance:.2f} >= min {min_trust:.2f}")
    else:
        reasons.append(f"FAIL: provenance {provenance:.2f} < min {min_trust:.2f}")
        failed = True

    # ── Check 5: Allowed sources ───────────────────────────────────────────
    if allowed_sources and len(allowed_sources) > 0:
        if source in allowed_sources:
            reasons.append(f"source '{source}' in allowed list")
        else:
            reasons.append(f"FAIL: source '{source}' not in {allowed_sources}")
            failed = True

    # ── Check 6: Exclude keywords ────────────────────────────────────────
    exclude_keywords = mandate.get("exclude_keywords") or []
    if exclude_keywords:
        title_lower = str(hit.get("title", "")).lower()
        matched = [kw for kw in exclude_keywords if kw.lower() in title_lower]
        if matched:
            reasons.append(f"FAIL: title contains excluded keyword(s): {matched}")
            failed = True
        else:
            reasons.append("no excluded keywords found in title")

    # ── Check 7: Not expired ───────────────────────────────────────────────
    if expires_at is not None:
        if isinstance(expires_at, str):
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                expires_dt = None
        elif isinstance(expires_at, datetime):
            expires_dt = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_dt = None

        if expires_dt is not None:
            if now < expires_dt:
                reasons.append("mandate not expired")
            else:
                reasons.append("FAIL: mandate expired")
                failed = True

    # ── Check 8: Cross-border availability ─────────────────────────────────
    if is_domestic_only and listing_region and mandate_region and listing_region != mandate_region:
        reasons.append(
            f"FAIL: domestic-only listing (ships from {listing_region}, user in {mandate_region})"
        )
        failed = True

    # ── Compute deal_score ─────────────────────────────────────────────────
    # deal_score = 0.35 * provenance + 0.30 * price_discount + 0.20 * recency + 0.15 * scarcity
    price_discount = 0.0
    price_vs_q50_pct = 0.0

    if prediction and prediction.get("q50"):
        q50 = float(prediction["q50"])
        if q50 > 0:
            price_vs_q50_pct = ((price - q50) / q50) * 100.0
            # Normalize discount to 0-1 (capped: 30% below = 1.0, at q50 = 0.0, above = 0.0)
            price_discount = max(0.0, min(1.0, -price_vs_q50_pct / 30.0))

    # Recency — newer listings score higher based on discovered_at
    discovered_at = hit.get("discovered_at")
    if discovered_at is not None:
        if isinstance(discovered_at, str):
            try:
                discovered_dt = datetime.fromisoformat(discovered_at.replace("Z", "+00:00"))
            except ValueError:
                discovered_dt = None
        elif isinstance(discovered_at, datetime):
            discovered_dt = discovered_at if discovered_at.tzinfo else discovered_at.replace(tzinfo=timezone.utc)
        else:
            discovered_dt = None

        if discovered_dt is not None:
            days_since = max(0, (now - discovered_dt).total_seconds() / 86400)
            recency_score = max(0.0, 1.0 - days_since / 30.0)
        else:
            recency_score = 0.5
    else:
        recency_score = 0.5

    # Scarcity/urgency — low quantity_available boosts deal score
    quantity = int(hit.get("quantity_available", 0) or 0)
    if quantity == 1:
        scarcity_score = 1.0
    elif quantity == 2:
        scarcity_score = 0.8
    elif 3 <= quantity <= 5:
        scarcity_score = 0.5
    elif quantity > 5:
        scarcity_score = 0.2
    else:
        scarcity_score = 0.5  # unknown quantity — neutral

    deal_score = min(1.0, 0.35 * provenance + 0.30 * price_discount + 0.20 * recency_score + 0.15 * scarcity_score)

    return PolicyVerdict(
        passed=not failed,
        reasons=reasons,
        deal_score=round(deal_score, 4),
        price_vs_q50_pct=round(price_vs_q50_pct, 1),
    )


def _fmt_eur(v: float) -> str:
    """Format a number as EUR string."""
    return f"\u20ac{v:,.2f}"
