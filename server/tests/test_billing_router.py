"""Tests for the billing router (Stripe integration)."""

from __future__ import annotations

import json
from collections import OrderedDict
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
        mock_pool.fetchrow.return_value = {"event_id": "evt_checkout_test_1"}  # INSERT succeeded (new event)

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp.status_code == 200
            assert resp.json()["received"] is True
            # fetchrow for dedup INSERT ... RETURNING, execute for checkout handler
            assert mock_pool.fetchrow.call_count >= 1  # dedup check
            assert mock_pool.execute.call_count >= 1   # subscription upsert

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
        # First fetchrow: dedup check (return row = new event)
        # Second fetchrow: sponsor_subscriptions check (return None = not a sponsor)
        mock_pool.fetchrow.side_effect = [{"event_id": "evt_deleted_test_1"}, None]

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp.status_code == 200
            # fetchrow for dedup check, execute for subscription handler UPDATE
            assert mock_pool.fetchrow.call_count >= 1
            assert mock_pool.execute.call_count >= 1
            # Verify the handler SQL contains 'free' and 'canceled'
            handler_calls = [c for c in mock_pool.execute.call_args_list
                           if "free" in str(c) and "canceled" in str(c)]
            assert len(handler_calls) >= 1

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
        # First fetchrow: dedup INSERT succeeds (new event, returns row)
        # Second fetchrow: dedup INSERT conflict (duplicate, returns None)
        mock_pool.fetchrow.side_effect = [
            {"event_id": "evt_dedup_test_1"},  # first call: new event
            None,                                # second call: duplicate (ON CONFLICT DO NOTHING)
        ]

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            # First call processes
            resp1 = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp1.status_code == 200
            assert resp1.json().get("duplicate") is None
            # fetchrow for dedup check, execute for checkout handler
            assert mock_pool.fetchrow.call_count >= 1
            assert mock_pool.execute.call_count >= 1
            first_execute_count = mock_pool.execute.call_count

            # Second call is deduped (DB INSERT returns None = already exists)
            resp2 = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )
            assert resp2.status_code == 200
            assert resp2.json()["duplicate"] is True
            # execute was NOT called again (deduped before reaching handler)
            assert mock_pool.execute.call_count == first_execute_count


class TestPlanLimits:
    """Verify PLAN_LIMITS structure."""

    def test_free_limits(self):
        """docs/MONETIZATION.md is the source; this only pins it.

        `max_mandates` is **0**, not 3, since 2026-07-31. Deal discovery is
        Pro-only — the worker skips free users' mandates entirely — so a
        mandate on the free plan can never produce a deal. The 3 it asserted
        were unreachable through the UI and inert if reached by deep link, and
        `/purchase/*` IS a Universal Link path.

        This assertion outlived the change by ~3 weeks. Anyone who "fixes" it
        by putting 3 back into PLAN_LIMITS reopens that hole and makes the
        paywall advertise a feature the buyer gets none of.
        """
        from app.routes.billing_router import PLAN_LIMITS
        free = PLAN_LIMITS["free"]
        assert free["max_mandates"] == 0
        assert free["deal_discovery"] is False
        assert free["dossier_pdf"] is False
        assert free["advanced_analytics"] is False

    def test_pro_limits(self):
        """`advanced_analytics` is **True** for Pro since 2026-07-28.

        False was a leftover from the three-tier model, where it was
        Premium-only. Premium folded into Pro and is no longer purchasable
        (RevenueCat sells only the `pro` entitlement), so while this stayed
        False NO user could ever be granted it. On the fallback path — no
        RevenueCat key, or RC reporting free — a paying Pro user was told
        advanced_analytics=False and Home's "Extended Portfolio Insights"
        button sent them to the paywall instead of /analytics.

        docs/MONETIZATION.md's plan table says Pro: Yes. The test was the last
        thing still claiming otherwise.
        """
        from app.routes.billing_router import PLAN_LIMITS
        pro = PLAN_LIMITS["pro"]
        assert pro["max_mandates"] == 10
        assert pro["deal_discovery"] is True
        assert pro["dossier_pdf"] is True
        assert pro["advanced_analytics"] is True

    def test_premium_limits(self):
        from app.routes.billing_router import PLAN_LIMITS
        premium = PLAN_LIMITS["premium"]
        assert premium["max_mandates"] == 50
        assert premium["deal_discovery"] is True
        assert premium["dossier_pdf"] is True
        assert premium["advanced_analytics"] is True


# ---------------------------------------------------------------------------
# The claim must be RELEASED when the work after it fails
#
# `_event_already_processed` claims the event id before any work, with an
# atomic INSERT ... ON CONFLICT DO NOTHING. Nothing ever deleted that row, so a
# failure after the claim was permanent: the provider's redelivery
# short-circuits on the claim and the work never happens. For RevenueCat that
# left a member CHARGED, in the revenue ledger, and on `free` — `get_user_plan`
# reads `subscriptions`, and nothing reconciles it from `subscription_events`
# (class sweep K, 2026-09-17).
# ---------------------------------------------------------------------------

class TestWebhookClaimIsReleasedOnFailure:
    def test_stripe_handler_failure_releases_the_claim(self, client):
        event = {
            "id": "evt_claim_release_1",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_test_999"}},
        }
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = event

        mock_pool = AsyncMock()
        mock_pool.fetchrow.side_effect = [{"event_id": "evt_claim_release_1"}, None]
        # The handler's write blows up after the claim was taken.
        mock_pool.execute.side_effect = RuntimeError("deadlock detected")

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )

        # Stripe must be told to retry...
        assert resp.status_code >= 500
        # ...and the claim must be gone, or the retry is a no-op.
        deletes = [
            c for c in mock_pool.execute.call_args_list
            if "DELETE FROM processed_webhook_events" in str(c.args[0])
        ]
        assert deletes, "the claim was never released — the retry will short-circuit"
        assert deletes[0].args[1] == "evt_claim_release_1"

    def test_revenuecat_subscriptions_failure_releases_the_claim(self, client):
        event = {
            "api_version": "1.0",
            "event": {
                "id": "evt_rc_claim_1",
                "type": "INITIAL_PURCHASE",
                "app_user_id": "11111111-1111-1111-1111-111111111111",
                "product_id": "sparrow_pro_monthly",
                "purchased_at_ms": 1_750_000_000_000,
                "store": "APP_STORE",
                "environment": "PRODUCTION",
                "price_in_purchased_currency": 4.99,
                "currency": "EUR",
                "entitlement_ids": ["pro"],
            },
        }

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"event_id": "evt_rc_claim_1"}
        mock_pool.fetchval.return_value = None

        # Ledger insert succeeds; the `subscriptions` upsert is the one that fails.
        calls: list[str] = []

        async def execute(sql, *args):
            calls.append(str(sql))
            if "INSERT INTO subscriptions" in str(sql):
                raise RuntimeError("unique violation")
            return "OK"

        mock_pool.execute.side_effect = execute

        async def fake_pool():
            return mock_pool

        with patch("app.routes.billing_router.DB_ENABLED", True), \
             patch("app.routes.billing_router.get_pool", fake_pool), \
             patch("app.routes.billing_router.REVENUECAT_WEBHOOK_AUTH", "test-secret"), \
             patch("app.routes.billing_router._rc_resolve_user_id",
                   AsyncMock(return_value="11111111-1111-1111-1111-111111111111")), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/revenuecat-webhook",
                content=json.dumps(event).encode(),
                headers={"Content-Type": "application/json", "Authorization": "test-secret"},
            )

        assert resp.status_code >= 500
        assert any("DELETE FROM processed_webhook_events" in c for c in calls), \
            "the claim was never released — the member stays on free forever"

    # The two paths 8439f97 missed. `docs/API.md` states the rule as "**any**
    # failure after the claim must release it", and these are failures after the
    # claim that did not.

    def test_revenuecat_ledger_failure_releases_the_claim(self, client):
        """The ledger insert is the FIRST write, and its 500 was unretryable.

        The handler's own comment says "500 so RevenueCat retries — losing a
        revenue event loses a payout". The retry could not run: the claim was
        still held, so the redelivery short-circuits at
        `_event_already_processed` and answers `{"ok": true, "duplicate": true}`.
        The payout row is lost for good, and `subscriptions` — which comes after
        the ledger — is never written either, so the member is charged and left
        on `free`. Worse than the case that was fixed, on the write the comment
        calls the source of truth.
        """
        event = {
            "api_version": "1.0",
            "event": {
                "id": "evt_rc_ledger_1",
                "type": "INITIAL_PURCHASE",
                "app_user_id": "22222222-2222-2222-2222-222222222222",
                "product_id": "sparrow_pro_monthly",
                "purchased_at_ms": 1_750_000_000_000,
                "store": "APP_STORE",
                "environment": "PRODUCTION",
                "price_in_purchased_currency": 4.99,
                "currency": "EUR",
                "entitlement_ids": ["pro"],
            },
        }

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"event_id": "evt_rc_ledger_1"}
        mock_pool.fetchval.return_value = None

        calls: list[str] = []

        async def execute(sql, *args):
            calls.append(str(sql))
            if "INSERT INTO subscription_events" in str(sql):
                raise RuntimeError("connection reset by peer")
            return "OK"

        mock_pool.execute.side_effect = execute

        async def fake_pool():
            return mock_pool

        with patch("app.routes.billing_router.DB_ENABLED", True), \
             patch("app.routes.billing_router.get_pool", fake_pool), \
             patch("app.routes.billing_router.REVENUECAT_WEBHOOK_AUTH", "test-secret"), \
             patch("app.routes.billing_router._rc_resolve_user_id",
                   AsyncMock(return_value="22222222-2222-2222-2222-222222222222")), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/revenuecat-webhook",
                content=json.dumps(event).encode(),
                headers={"Content-Type": "application/json", "Authorization": "test-secret"},
            )

        assert resp.status_code >= 500
        assert any("DELETE FROM processed_webhook_events" in c for c in calls), \
            "the claim was never released — the revenue event is lost for good"

    def test_revenuecat_user_lookup_failure_releases_the_claim(self, client):
        """A failure BETWEEN the claim and the first write also has to release.

        `_rc_resolve_user_id` runs after the claim and touches the database, so
        it can raise for the same reasons any query can. Nothing caught it, so
        the 500 went back to RevenueCat with the claim held: the event is
        swallowed on redelivery with neither row written.
        """
        event = {
            "api_version": "1.0",
            "event": {
                "id": "evt_rc_lookup_1",
                "type": "INITIAL_PURCHASE",
                "app_user_id": "33333333-3333-3333-3333-333333333333",
                "product_id": "sparrow_pro_monthly",
                "purchased_at_ms": 1_750_000_000_000,
                "store": "APP_STORE",
                "environment": "PRODUCTION",
                "price_in_purchased_currency": 4.99,
                "currency": "EUR",
                "entitlement_ids": ["pro"],
            },
        }

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"event_id": "evt_rc_lookup_1"}

        calls: list[str] = []

        async def execute(sql, *args):
            calls.append(str(sql))
            return "OK"

        mock_pool.execute.side_effect = execute

        async def fake_pool():
            return mock_pool

        with patch("app.routes.billing_router.DB_ENABLED", True), \
             patch("app.routes.billing_router.get_pool", fake_pool), \
             patch("app.routes.billing_router.REVENUECAT_WEBHOOK_AUTH", "test-secret"), \
             patch("app.routes.billing_router._rc_resolve_user_id",
                   AsyncMock(side_effect=RuntimeError("pool timeout"))), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/revenuecat-webhook",
                content=json.dumps(event).encode(),
                headers={"Content-Type": "application/json", "Authorization": "test-secret"},
            )

        assert resp.status_code >= 500
        assert any("DELETE FROM processed_webhook_events" in c for c in calls), \
            "the claim was never released — the event is swallowed on redelivery"

    def test_a_successful_revenuecat_event_keeps_its_claim(self, client):
        """The chokepoint must not release on the way OUT.

        A release on success would undo the dedup it exists to protect: the next
        redelivery of the same event would run the whole handler again. The
        writes are idempotent, so this would not corrupt anything — which is
        exactly why a test has to say it, since nothing would look broken.
        """
        event = {
            "api_version": "1.0",
            "event": {
                "id": "evt_rc_ok_1",
                "type": "INITIAL_PURCHASE",
                "app_user_id": "44444444-4444-4444-4444-444444444444",
                "product_id": "sparrow_pro_monthly",
                "purchased_at_ms": 1_750_000_000_000,
                "store": "APP_STORE",
                "environment": "PRODUCTION",
                "price_in_purchased_currency": 4.99,
                "currency": "EUR",
                "entitlement_ids": ["pro"],
            },
        }

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {"event_id": "evt_rc_ok_1"}
        mock_pool.fetchval.return_value = None

        calls: list[str] = []

        async def execute(sql, *args):
            calls.append(str(sql))
            return "OK"

        mock_pool.execute.side_effect = execute

        async def fake_pool():
            return mock_pool

        with patch("app.routes.billing_router.DB_ENABLED", True), \
             patch("app.routes.billing_router.get_pool", fake_pool), \
             patch("app.routes.billing_router.REVENUECAT_WEBHOOK_AUTH", "test-secret"), \
             patch("app.routes.billing_router._rc_resolve_user_id",
                   AsyncMock(return_value="44444444-4444-4444-4444-444444444444")), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/revenuecat-webhook",
                content=json.dumps(event).encode(),
                headers={"Content-Type": "application/json", "Authorization": "test-secret"},
            )

        assert resp.status_code == 200
        assert any("INSERT INTO subscription_events" in c for c in calls)
        assert any("INSERT INTO subscriptions" in c for c in calls)
        assert not any("DELETE FROM processed_webhook_events" in c for c in calls), \
            "the claim was released on SUCCESS — the next redelivery reprocesses it"

    def test_stripe_malformed_payload_after_the_claim_releases_it(self, client):
        """`event["data"]["object"]` sat between the claim and the try block.

        A signed event whose shape we did not expect raised KeyError there, which
        is a failure after the claim like any other: 500 to Stripe, claim held,
        redelivery swallowed. The signature was valid, so this is Stripe's own
        payload changing shape, not an attack.
        """
        event = {"id": "evt_stripe_malformed_1", "type": "customer.subscription.deleted"}
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = event

        mock_pool = AsyncMock()
        mock_pool.fetchrow.side_effect = [{"event_id": "evt_stripe_malformed_1"}, None]

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=mock_pool), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()):
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )

        assert resp.status_code >= 500
        deletes = [
            c for c in mock_pool.execute.call_args_list
            if "DELETE FROM processed_webhook_events" in str(c.args[0])
        ]
        assert deletes, "the claim was never released — the retry will short-circuit"

    def test_stripe_without_a_database_does_not_answer_received(self, client):
        """No database means no success — `docs/API.md`, and Stripe is a write.

        The handler answered 200 `{"received": true}` with the claim taken and
        nothing written. 200 is Stripe's signal to stop retrying, so a paid
        sponsorship, ticket or plan change arriving during a database outage was
        acknowledged and dropped. The RevenueCat handler already 503s here.
        """
        event = {
            "id": "evt_stripe_nodb_1",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_test_nodb"}},
        }
        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = event

        with patch("app.routes.billing_router.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("app.routes.billing_router._get_stripe", return_value=mock_stripe), \
             patch("app.routes.billing_router.get_pool", return_value=None), \
             patch("app.routes.billing_router._SEEN_EVENTS", OrderedDict()) as seen:
            resp = client.post(
                "/billing/webhook",
                content=json.dumps(event).encode(),
                headers={"Stripe-Signature": "valid_sig"},
            )

        assert resp.status_code == 503, "200 tells Stripe to stop retrying"
        assert "evt_stripe_nodb_1" not in seen, \
            "the in-memory claim outlived the failure — the retry is swallowed"
