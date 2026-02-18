"""Tests for the billing router (Stripe integration)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient with DEV_MODE=true for auth bypass."""
    import os
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    from main import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /billing/status
# ---------------------------------------------------------------------------

class TestBillingStatus:
    """GET /billing/status — returns subscription plan and limits."""

    def test_dev_mode_returns_premium(self, client):
        """In DEV_MODE with DB_ENABLED=false, return premium access."""
        resp = client.get("/billing/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "premium"
        assert data["status"] == "active"
        assert data["limits"]["deal_discovery"] is True
        assert data["limits"]["dossier_pdf"] is True
        assert data["limits"]["advanced_analytics"] is True
        assert data["limits"]["max_mandates"] == 50

    def test_v1_alias(self, client):
        """GET /v1/billing/status also works."""
        resp = client.get("/v1/billing/status")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "premium"


# ---------------------------------------------------------------------------
# POST /billing/checkout-session
# ---------------------------------------------------------------------------

class TestCheckoutSession:
    """POST /billing/checkout-session."""

    def test_billing_not_configured(self, client):
        """Without STRIPE_SECRET_KEY, return 503."""
        with patch("app.routes.billing_router.STRIPE_SECRET_KEY", ""):
            resp = client.post(
                "/billing/checkout-session",
                json={"plan": "pro"},
            )
            assert resp.status_code == 503

    def test_invalid_plan(self, client):
        """Invalid plan name returns 400."""
        with patch("app.routes.billing_router.STRIPE_SECRET_KEY", "sk_test_123"), \
             patch("app.routes.billing_router._get_stripe") as mock_stripe, \
             patch("app.routes.billing_router.DB_ENABLED", True):
            mock_stripe.return_value = MagicMock()
            resp = client.post(
                "/billing/checkout-session",
                json={"plan": "invalid"},
            )
            assert resp.status_code == 400

    def test_db_disabled_returns_503(self, client):
        """DB_ENABLED=false with Stripe configured still returns 503."""
        with patch("app.routes.billing_router.STRIPE_SECRET_KEY", "sk_test_123"), \
             patch("app.routes.billing_router._get_stripe") as mock_stripe, \
             patch("app.routes.billing_router.DB_ENABLED", False):
            mock_stripe.return_value = MagicMock()
            resp = client.post(
                "/billing/checkout-session",
                json={"plan": "pro"},
            )
            assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /billing/portal-session
# ---------------------------------------------------------------------------

class TestPortalSession:
    """POST /billing/portal-session."""

    def test_billing_not_configured(self, client):
        """Without STRIPE_SECRET_KEY, return 503."""
        with patch("app.routes.billing_router.STRIPE_SECRET_KEY", ""):
            resp = client.post("/billing/portal-session")
            assert resp.status_code == 503

    def test_no_subscription_returns_404(self, client):
        """No billing account returns 404."""
        with patch("app.routes.billing_router.STRIPE_SECRET_KEY", "sk_test_123"), \
             patch("app.routes.billing_router._get_stripe") as mock_stripe, \
             patch("app.routes.billing_router.DB_ENABLED", True), \
             patch("app.routes.billing_router._get_subscription", new_callable=AsyncMock, return_value=None):
            mock_stripe.return_value = MagicMock()
            resp = client.post("/billing/portal-session")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /billing/webhook
# ---------------------------------------------------------------------------

class TestWebhook:
    """POST /billing/webhook — Stripe webhook signature verification."""

    def test_webhook_not_configured(self, client):
        """Without STRIPE_WEBHOOK_SECRET, return 503."""
        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", ""):
            resp = client.post(
                "/billing/webhook",
                content=b"{}",
                headers={"Stripe-Signature": "test"},
            )
            assert resp.status_code == 503

    def test_invalid_signature(self, client):
        """Invalid webhook signature returns 400."""
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.side_effect = ValueError("bad sig")

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe):
            resp = client.post(
                "/billing/webhook",
                content=b'{"type":"test"}',
                headers={"Stripe-Signature": "bad_sig"},
            )
            assert resp.status_code == 400

    def test_valid_checkout_completed(self, client):
        """Valid checkout.session.completed event is processed."""
        event = {
            "id": "evt_checkout_test_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"user_id": "user-123", "plan": "pro"},
                    "customer": "cus_test",
                    "subscription": "sub_test",
                }
            },
        }
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = event

        mock_pool = AsyncMock()

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool):
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp.status_code == 200
            assert resp.json()["received"] is True
            mock_pool.execute.assert_called_once()

    def test_subscription_deleted_event(self, client):
        """customer.subscription.deleted downgrades to free."""
        event = {
            "id": "evt_deleted_test_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_123",
                }
            },
        }
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = event

        mock_pool = AsyncMock()

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool):
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp.status_code == 200
            mock_pool.execute.assert_called_once()
            # Verify the SQL contains 'free' and 'canceled'
            sql_arg = mock_pool.execute.call_args[0][0]
            assert "free" in sql_arg
            assert "canceled" in sql_arg


# ---------------------------------------------------------------------------
# PLAN_LIMITS
# ---------------------------------------------------------------------------

    def test_duplicate_event_is_skipped(self, client):
        """Second delivery of the same event is skipped (idempotency)."""
        event = {
            "id": "evt_dedup_test_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"user_id": "user-dedup", "plan": "pro"},
                    "customer": "cus_dedup",
                    "subscription": "sub_dedup",
                }
            },
        }
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = event
        mock_pool = AsyncMock()

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool):
            # First call processes
            resp1 = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp1.status_code == 200
            assert resp1.json().get("duplicate") is None
            assert mock_pool.execute.call_count == 1

            # Second call is deduped
            resp2 = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp2.status_code == 200
            assert resp2.json()["duplicate"] is True
            # execute was NOT called again
            assert mock_pool.execute.call_count == 1


class TestPlanLimits:
    """Verify PLAN_LIMITS structure."""

    def test_free_limits(self):
        from app.routes.billing_router import PLAN_LIMITS
        free = PLAN_LIMITS["free"]
        assert free["max_mandates"] == 3
        assert free["deal_discovery"] is False
        assert free["dossier_pdf"] is False
        assert free["advanced_analytics"] is False

    def test_pro_limits(self):
        from app.routes.billing_router import PLAN_LIMITS
        pro = PLAN_LIMITS["pro"]
        assert pro["max_mandates"] == 10
        assert pro["deal_discovery"] is True
        assert pro["dossier_pdf"] is True
        assert pro["advanced_analytics"] is False

    def test_premium_limits(self):
        from app.routes.billing_router import PLAN_LIMITS
        premium = PLAN_LIMITS["premium"]
        assert premium["max_mandates"] == 50
        assert premium["deal_discovery"] is True
        assert premium["dossier_pdf"] is True
        assert premium["advanced_analytics"] is True
