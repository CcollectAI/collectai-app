"""Tests for app.subscription — subscription gating dependency."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    import os
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestGetUserPlan:
    """get_user_plan() returns the correct plan based on DB state."""

    @pytest.mark.asyncio
    async def test_dev_mode_returns_premium(self):
        with patch("app.subscription.DEV_MODE", True), \
             patch("app.subscription.DB_ENABLED", False):
            from app.subscription import get_user_plan
            plan = await get_user_plan("user-123")
            assert plan == "premium"

    @pytest.mark.asyncio
    async def test_db_disabled_returns_free(self):
        with patch("app.subscription.DEV_MODE", False), \
             patch("app.subscription.DB_ENABLED", False):
            from app.subscription import get_user_plan
            plan = await get_user_plan("user-123")
            assert plan == "free"

    @pytest.mark.asyncio
    async def test_no_subscription_row_returns_free(self):
        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = None

        with patch("app.subscription.DEV_MODE", False), \
             patch("app.subscription.DB_ENABLED", True), \
             patch("app.subscription.get_pool", return_value=mock_pool):
            from app.subscription import get_user_plan
            plan = await get_user_plan("user-123")
            assert plan == "free"

    @pytest.mark.asyncio
    async def test_active_pro_returns_pro(self):
        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"plan": "pro"}

        with patch("app.subscription.DEV_MODE", False), \
             patch("app.subscription.DB_ENABLED", True), \
             patch("app.subscription.get_pool", return_value=mock_pool):
            from app.subscription import get_user_plan
            plan = await get_user_plan("user-123")
            assert plan == "pro"

    @pytest.mark.asyncio
    async def test_active_premium_returns_premium(self):
        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"plan": "premium"}

        with patch("app.subscription.DEV_MODE", False), \
             patch("app.subscription.DB_ENABLED", True), \
             patch("app.subscription.get_pool", return_value=mock_pool):
            from app.subscription import get_user_plan
            plan = await get_user_plan("user-123")
            assert plan == "premium"


class TestGetUserMandateLimit:
    """get_user_mandate_limit() returns correct limits per plan."""

    @pytest.mark.asyncio
    async def test_free_user_gets_0(self):
        """0 since 2026-07-31 — see docs/MONETIZATION.md and the note on
        TestPlanLimits.test_free_limits. `get_user_mandate_limit` reads
        PLAN_LIMITS rather than declaring its own number, so there is one
        source of truth and this is a pin, not a second one.

        The old name encoded the number, which is why it survived the change
        looking plausible.
        """
        with patch("app.subscription.get_user_plan", new_callable=AsyncMock, return_value="free"):
            from app.subscription import get_user_mandate_limit
            limit = await get_user_mandate_limit("user-123")
            assert limit == 0

    @pytest.mark.asyncio
    async def test_pro_user_gets_10(self):
        with patch("app.subscription.get_user_plan", new_callable=AsyncMock, return_value="pro"):
            from app.subscription import get_user_mandate_limit
            limit = await get_user_mandate_limit("user-123")
            assert limit == 10

    @pytest.mark.asyncio
    async def test_premium_user_gets_50(self):
        with patch("app.subscription.get_user_plan", new_callable=AsyncMock, return_value="premium"):
            from app.subscription import get_user_mandate_limit
            limit = await get_user_mandate_limit("user-123")
            assert limit == 50


class TestRequirePlan:
    """require_plan() dependency rejects insufficient plans."""

    def test_dossier_export_gated_for_free_plan(self, client):
        """Dossier export should reject free users."""
        with patch("app.subscription.get_user_plan", new_callable=AsyncMock, return_value="free"), \
             patch("app.subscription.DB_ENABLED", True):
            resp = client.get("/dossier/test-item-id/export")
            assert resp.status_code == 403

    def test_dossier_export_allowed_for_pro(self, client):
        """Dossier export should work for pro users (will fail on DB but not on plan check)."""
        with patch("app.subscription.get_user_plan", new_callable=AsyncMock, return_value="pro"):
            resp = client.get("/dossier/test-item-id/export")
            # Will get 503 (db not available) or 404, but NOT 403
            assert resp.status_code != 403


class TestPlanRanks:
    """Verify plan hierarchy."""

    def test_plan_ranks(self):
        from app.subscription import _PLAN_RANK
        assert _PLAN_RANK["free"] < _PLAN_RANK["pro"] < _PLAN_RANK["premium"]
