"""
Tests for app/agents/policy_engine.py — PolicyEngine.

Covers:
  - Price within max_price
  - Budget constraint
  - Cooldown enforcement
  - Trust score check
  - Allowed sources filtering
  - Expiration check
  - Deal score computation
  - Price vs q50 percentage
  - All-passing verdict
  - Multiple failures at once
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.agents.policy_engine import evaluate, PolicyVerdict


def _base_mandate(**overrides):
    m = {
        "max_price": 400.0,
        "max_total_budget": None,
        "spent_total": 0.0,
        "min_trust_score": 0.60,
        "cooldown_hours": 24,
        "allowed_sources": [],
        "expires_at": None,
        "last_deal_at": None,
    }
    m.update(overrides)
    return m


def _base_hit(**overrides):
    h = {
        "price": 350.0,
        "source": "ebay",
        "provenance_score": 0.85,
        "url": "https://www.ebay.com/itm/123",
        "title": "Charizard PSA 10",
        "condition": "Near Mint",
        "currency": "EUR",
    }
    h.update(overrides)
    return h


class TestPriceCheck:
    def test_price_within_limit(self):
        v = evaluate(_base_mandate(), _base_hit(price=300))
        assert v.passed
        assert any("price" in r and "<=" in r for r in v.reasons)

    def test_price_exceeds_limit(self):
        v = evaluate(_base_mandate(max_price=200), _base_hit(price=300))
        assert not v.passed
        assert any("FAIL" in r and "price" in r for r in v.reasons)

    def test_price_exactly_at_limit(self):
        v = evaluate(_base_mandate(max_price=350), _base_hit(price=350))
        assert v.passed


class TestBudgetCheck:
    def test_no_budget_set(self):
        v = evaluate(_base_mandate(max_total_budget=None), _base_hit())
        assert v.passed
        # No budget reason should appear
        assert not any("budget" in r.lower() for r in v.reasons if "FAIL" in r)

    def test_within_budget(self):
        v = evaluate(_base_mandate(max_total_budget=1000, spent_total=100), _base_hit(price=200))
        assert v.passed
        assert any("budget OK" in r for r in v.reasons)

    def test_exceeds_budget(self):
        v = evaluate(_base_mandate(max_total_budget=500, spent_total=400), _base_hit(price=200))
        assert not v.passed
        assert any("FAIL" in r and "budget" in r for r in v.reasons)


class TestCooldown:
    def test_no_previous_deal(self):
        v = evaluate(_base_mandate(last_deal_at=None), _base_hit())
        assert v.passed  # No cooldown to violate

    def test_cooldown_passed(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        v = evaluate(_base_mandate(last_deal_at=old, cooldown_hours=24), _base_hit())
        assert v.passed
        assert any("cooldown OK" in r for r in v.reasons)

    def test_cooldown_not_passed(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        v = evaluate(_base_mandate(last_deal_at=recent, cooldown_hours=24), _base_hit())
        assert not v.passed
        assert any("FAIL" in r and "cooldown" in r for r in v.reasons)


class TestTrustScore:
    def test_above_minimum(self):
        v = evaluate(_base_mandate(min_trust_score=0.60), _base_hit(provenance_score=0.85))
        assert v.passed

    def test_below_minimum(self):
        v = evaluate(_base_mandate(min_trust_score=0.90), _base_hit(provenance_score=0.50))
        assert not v.passed
        assert any("FAIL" in r and "provenance" in r for r in v.reasons)


class TestAllowedSources:
    def test_empty_allows_all(self):
        v = evaluate(_base_mandate(allowed_sources=[]), _base_hit(source="ebay"))
        assert v.passed

    def test_source_in_list(self):
        v = evaluate(_base_mandate(allowed_sources=["ebay", "tcgplayer"]), _base_hit(source="ebay"))
        assert v.passed

    def test_source_not_in_list(self):
        v = evaluate(_base_mandate(allowed_sources=["tcgplayer"]), _base_hit(source="ebay"))
        assert not v.passed
        assert any("FAIL" in r and "source" in r for r in v.reasons)


class TestExpiration:
    def test_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        v = evaluate(_base_mandate(expires_at=future), _base_hit())
        assert v.passed

    def test_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        v = evaluate(_base_mandate(expires_at=past), _base_hit())
        assert not v.passed
        assert any("FAIL" in r and "expired" in r for r in v.reasons)

    def test_no_expiration(self):
        v = evaluate(_base_mandate(expires_at=None), _base_hit())
        assert v.passed


class TestDealScore:
    def test_score_is_between_0_and_1(self):
        v = evaluate(_base_mandate(), _base_hit())
        assert 0.0 <= v.deal_score <= 1.0

    def test_score_with_prediction(self):
        pred = {"q10": 300, "q50": 400, "q90": 500}
        v = evaluate(_base_mandate(), _base_hit(price=300), pred)
        assert v.deal_score > 0
        assert v.price_vs_q50_pct < 0  # Below median

    def test_score_without_prediction(self):
        v = evaluate(_base_mandate(), _base_hit(), None)
        assert v.price_vs_q50_pct == 0.0

    def test_price_vs_q50_pct(self):
        pred = {"q10": 300, "q50": 400, "q90": 500}
        v = evaluate(_base_mandate(), _base_hit(price=340), pred)
        # (340 - 400) / 400 * 100 = -15.0
        assert v.price_vs_q50_pct == -15.0


class TestMultipleFailures:
    def test_several_failures_at_once(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        v = evaluate(
            _base_mandate(
                max_price=100,
                min_trust_score=0.99,
                expires_at=past,
            ),
            _base_hit(price=500, provenance_score=0.10),
        )
        assert not v.passed
        fail_count = sum(1 for r in v.reasons if "FAIL" in r)
        assert fail_count >= 3


class TestAllPassing:
    def test_everything_passes(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        old_deal = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        v = evaluate(
            _base_mandate(
                max_price=500,
                max_total_budget=5000,
                spent_total=100,
                min_trust_score=0.50,
                cooldown_hours=24,
                allowed_sources=["ebay"],
                expires_at=future,
                last_deal_at=old_deal,
            ),
            _base_hit(price=350, source="ebay", provenance_score=0.85),
            {"q10": 300, "q50": 400, "q90": 500},
        )
        assert v.passed
        assert not any("FAIL" in r for r in v.reasons)
        assert v.deal_score > 0
        assert v.price_vs_q50_pct < 0
