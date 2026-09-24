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

import re

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
    # One record per check the member can understand — {"code", "ok", ...numbers}.
    # The app renders these as sentences in the member's language; `reasons`
    # (engine strings like "total €28.13 … <= max €30.0") stay for the audit
    # trail and are no longer shown (2026-09-24).
    checks: list[dict] = field(default_factory=list)


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
    checks: list[dict] = []
    failed = False

    price = float(hit.get("price", 0) or 0)
    shipping_cost = float(hit.get("shipping_cost", 0) or 0)
    total_cost = price + shipping_cost
    # An ESTIMATED shipping cost is a guess (a regional midpoint), not the
    # listing's. It used to be added to the price and fail the budget: a €12.27
    # card "cost" €34.77 against a €30 limit because of €22.50 we invented —
    # 6 of 39 rejections on one test mandate (2026-09-24). A guess now never
    # decides the verdict; it is shown as a range for the member to check.
    shipping_estimated = bool(hit.get("shipping_estimated"))
    budget_cost = price if shipping_estimated else total_cost
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

    # ── Check 1: Total cost (price + stated shipping) within max_price ─────
    within = budget_cost <= max_price
    if shipping_estimated:
        reasons.append(
            f"{'' if within else 'FAIL: '}price {_fmt_eur(price)} {'<=' if within else '>'} max {_fmt_eur(max_price)}"
            f" (shipping not stated; estimate {_fmt_eur(shipping_cost)} not counted)"
        )
    elif shipping_cost > 0:
        reasons.append(
            f"{'' if within else 'FAIL: '}total {_fmt_eur(total_cost)} (price {_fmt_eur(price)} + shipping {_fmt_eur(shipping_cost)}) {'<=' if within else '>'} max {_fmt_eur(max_price)}"
        )
    else:
        reasons.append(f"{'' if within else 'FAIL: '}price {_fmt_eur(price)} {'<=' if within else '>'} max {_fmt_eur(max_price)}")
    if not within:
        failed = True
    checks.append({
        "code": "price", "ok": within, "price": round(price, 2), "max": round(max_price, 2),
        "shipping": None if shipping_estimated else round(shipping_cost, 2),
        "shipping_estimated": shipping_estimated,
        "shipping_min": hit.get("shipping_min") if shipping_estimated else None,
        "shipping_max": hit.get("shipping_max") if shipping_estimated else None,
    })

    # ── Check 2: Budget not exceeded (using total cost) ────────────────────
    if max_budget is not None:
        max_budget_f = float(max_budget)
        remaining = max_budget_f - spent
        budget_ok = spent + budget_cost <= max_budget_f
        if budget_ok:
            reasons.append(f"budget OK: {_fmt_eur(remaining)} remaining")
        else:
            reasons.append(
                f"FAIL: budget exceeded ({_fmt_eur(spent)} + {_fmt_eur(budget_cost)} > {_fmt_eur(max_budget_f)})"
            )
            failed = True
        checks.append({"code": "budget", "ok": budget_ok, "remaining": round(remaining, 2)})

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
                # Elapsed, not remaining: this printed the hours LEFT in the
                # window as "last deal Xh ago" — 23.6h "ago" for a deal found
                # 25 minutes earlier (2026-09-24).
                hours_ago = elapsed.total_seconds() / 3600
                reasons.append(
                    f"cooldown note: mandate last deal {hours_ago:.1f}h ago, inside its "
                    f"{cooldown_hours}h window (advisory; per-listing cooldown still applies)"
                )

    # ── Check 4: Trust score ───────────────────────────────────────────────
    if provenance >= min_trust:
        reasons.append(f"provenance {provenance:.2f} >= min {min_trust:.2f}")
    else:
        reasons.append(f"FAIL: provenance {provenance:.2f} < min {min_trust:.2f}")
        failed = True
    checks.append({"code": "trust", "ok": provenance >= min_trust})

    # ── Check 5: Allowed sources ───────────────────────────────────────────
    if allowed_sources and len(allowed_sources) > 0:
        if source in allowed_sources:
            reasons.append(f"source '{source}' in allowed list")
        else:
            reasons.append(f"FAIL: source '{source}' not in {allowed_sources}")
            failed = True
        checks.append({"code": "source", "ok": source in allowed_sources, "source": source})

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
        checks.append({"code": "keywords", "ok": not matched})

    # ── Check 6b: Same card, when the mandate is keyed ─────────────────────
    # A keyed mandate says WHICH card. The search query is the card's name, and
    # names repeat: "Charizard ex" returned SVP #161 (the key) but also Paldean
    # Fates #054 and Obsidian Flames #125, and all three passed as deals
    # (walked 2026-09-24). A title that STATES a card number other than the
    # key's is a different card. Only explicit forms count ("054/091", "#125",
    # "SVP - 161"): bare numbers are too often a set ("151") or a year.
    key_number = _key_card_number(mandate.get("canonical_ref"))
    if key_number:
        stated = _stated_card_numbers(str(hit.get("title", "")))
        if stated and key_number not in stated:
            reasons.append(f"FAIL: title states card #{'/#'.join(sorted(stated))}, not #{key_number}")
            failed = True
        elif stated:
            reasons.append(f"card #{key_number} matches the title")
        if stated:
            checks.append({"code": "card", "ok": key_number in stated, "number": key_number})

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
                checks.append({"code": "expired", "ok": False})

    # ── Check 8: Cross-border availability ─────────────────────────────────
    if is_domestic_only and listing_region and mandate_region and listing_region != mandate_region:
        reasons.append(
            f"FAIL: domestic-only listing (ships from {listing_region}, user in {mandate_region})"
        )
        failed = True
        checks.append({"code": "region", "ok": False})

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
        checks=checks,
        deal_score=round(deal_score, 4),
        price_vs_q50_pct=round(price_vs_q50_pct, 1),
    )


def _fmt_eur(v: float) -> str:
    """Format a number as EUR string."""
    return f"\u20ac{v:,.2f}"

_SLASH_NUM = re.compile(r"(?<![\d.])(\d{1,4})\s*/\s*\d{1,4}(?![\d])")
_HASH_NUM = re.compile(r"#\s*(\d{1,4})\b")
_CODE_NUM = re.compile(r"\b[A-Za-z]{2,6}\d{0,2}(?:pt\d)?\s*-\s*(\d{1,4})\b")


def _norm_num(n: str) -> str:
    return n.lstrip("0") or "0"


def _key_card_number(canonical_ref: Optional[str]) -> Optional[str]:
    """'pokemon:svp-svp-161' -> '161'; None when the key does not end in a number."""
    if not canonical_ref:
        return None
    last = str(canonical_ref).rsplit(":", 1)[-1].rsplit("-", 1)[-1]
    return _norm_num(last) if last.isdigit() else None


def _stated_card_numbers(title: str) -> set[str]:
    """Card numbers a listing title states explicitly."""
    found = set()
    for rx in (_SLASH_NUM, _HASH_NUM, _CODE_NUM):
        for m in rx.finditer(title):
            found.add(_norm_num(m.group(1)))
    return found
