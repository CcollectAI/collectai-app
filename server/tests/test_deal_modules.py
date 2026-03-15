"""Tests for deal desk split modules: deal_risk and deal_completion.

Verifies:
- compute_trust_badge returns correct badges for various scores
- compute_trust_score computes expected values
- deal_risk and deal_completion modules can be imported
- deal_desk_router still imports and has expected routes
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------

class TestDealModuleImports:
    def test_deal_risk_importable(self):
        from app.agents.deal_risk import (
            compute_trust_badge,
            compute_trust_score,
            get_reputation_data,
            compute_risk_flags,
        )
        assert callable(compute_trust_badge)
        assert callable(compute_trust_score)
        assert callable(get_reputation_data)
        assert callable(compute_risk_flags)

    def test_deal_completion_importable(self):
        from app.agents.deal_completion import execute_ship, execute_complete
        assert callable(execute_ship)
        assert callable(execute_complete)

    def test_deal_desk_router_importable(self):
        from app.agents.deal_desk_router import router
        assert router is not None

    def test_deal_desk_router_has_expected_routes(self):
        """Verify the router has all expected endpoint paths."""
        from app.agents.deal_desk_router import router

        route_paths = [r.path for r in router.routes]
        expected_paths = [
            "/deals/offer",
            "/deals/{offer_id}/counter",
            "/deals/{offer_id}/respond",
            "/deals/{offer_id}/cancel",
            "/deals/{offer_id}/ship",
            "/deals/{offer_id}/complete",
            "/deals/active",
            "/deals/history",
            "/deals/{offer_id}",
            "/deals/{offer_id}/evidence",
            "/deals/reputation/{target_user_id}",
            "/deals/{offer_id}/risk-flags",
        ]
        for path in expected_paths:
            assert path in route_paths, f"Missing route: {path}"


# ---------------------------------------------------------------------------
# compute_trust_badge
# ---------------------------------------------------------------------------

class TestComputeTrustBadge:
    def test_verified_badge(self):
        from app.agents.deal_risk import compute_trust_badge
        assert compute_trust_badge(completed=50, avg_stars=4.8) == "verified"
        assert compute_trust_badge(completed=100, avg_stars=5.0) == "verified"

    def test_power_badge(self):
        from app.agents.deal_risk import compute_trust_badge
        assert compute_trust_badge(completed=20, avg_stars=4.5) == "power"
        assert compute_trust_badge(completed=30, avg_stars=4.6) == "power"

    def test_regular_badge(self):
        from app.agents.deal_risk import compute_trust_badge
        assert compute_trust_badge(completed=5, avg_stars=3.0) == "regular"
        assert compute_trust_badge(completed=10, avg_stars=4.0) == "regular"

    def test_new_badge(self):
        from app.agents.deal_risk import compute_trust_badge
        assert compute_trust_badge(completed=0, avg_stars=0.0) == "new"
        assert compute_trust_badge(completed=4, avg_stars=5.0) == "new"

    def test_boundary_verified_needs_both_conditions(self):
        from app.agents.deal_risk import compute_trust_badge
        # 50 deals but low rating => power (not verified)
        assert compute_trust_badge(completed=50, avg_stars=4.5) == "power"
        # High rating but not enough deals
        assert compute_trust_badge(completed=20, avg_stars=4.8) == "power"

    def test_boundary_power_needs_both_conditions(self):
        from app.agents.deal_risk import compute_trust_badge
        # 20 deals but low rating => regular
        assert compute_trust_badge(completed=20, avg_stars=4.0) == "regular"

    def test_boundary_regular_exactly_5(self):
        from app.agents.deal_risk import compute_trust_badge
        assert compute_trust_badge(completed=5, avg_stars=0.0) == "regular"


# ---------------------------------------------------------------------------
# compute_trust_score
# ---------------------------------------------------------------------------

class TestComputeTrustScore:
    def test_zero_completed_returns_zero(self):
        from app.agents.deal_risk import compute_trust_score
        assert compute_trust_score(avg_stars=5.0, completed=0) == 0.0

    def test_negative_completed_returns_zero(self):
        from app.agents.deal_risk import compute_trust_score
        assert compute_trust_score(avg_stars=5.0, completed=-1) == 0.0

    def test_perfect_score_with_many_deals(self):
        from app.agents.deal_risk import compute_trust_score
        # (5/5)*80 + min(20, 50*2) = 80 + 20 = 100
        score = compute_trust_score(avg_stars=5.0, completed=50)
        assert score == 100.0

    def test_capped_at_100(self):
        from app.agents.deal_risk import compute_trust_score
        score = compute_trust_score(avg_stars=5.0, completed=1000)
        assert score == 100.0

    def test_low_rating_few_deals(self):
        from app.agents.deal_risk import compute_trust_score
        # (3/5)*80 + min(20, 2*2) = 48 + 4 = 52
        score = compute_trust_score(avg_stars=3.0, completed=2)
        assert abs(score - 52.0) < 0.01

    def test_one_completed_deal(self):
        from app.agents.deal_risk import compute_trust_score
        # (4/5)*80 + min(20, 1*2) = 64 + 2 = 66
        score = compute_trust_score(avg_stars=4.0, completed=1)
        assert abs(score - 66.0) < 0.01

    def test_trade_count_boost_caps_at_20(self):
        from app.agents.deal_risk import compute_trust_score
        # With 10 trades: min(20, 10*2) = 20 (capped)
        # With 5 trades: min(20, 5*2) = 10
        score_10 = compute_trust_score(avg_stars=4.0, completed=10)
        score_5 = compute_trust_score(avg_stars=4.0, completed=5)
        assert score_10 > score_5
        # Both should differ by exactly 10 (trade boost: 20 vs 10)
        assert abs((score_10 - score_5) - 10.0) < 0.01

    def test_returns_float(self):
        from app.agents.deal_risk import compute_trust_score
        result = compute_trust_score(avg_stars=4.5, completed=3)
        assert isinstance(result, float)
