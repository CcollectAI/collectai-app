"""Tests for app/features/sponsor_company_router.py — sponsor company CRUD endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
Most endpoints return 503 (DB not available) or validate input in offline mode.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

VALID_UUID = "00000000-0000-0000-0000-000000000099"


# ---------------------------------------------------------------------------
# GET /sponsor-companies/mine — list my companies
# ---------------------------------------------------------------------------

class TestListMyCompanies:
    def test_list_mine_returns_200(self):
        """Returns 200 with empty list when no DB pool."""
        resp = client.get("/sponsor-companies/mine")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data == []


# ---------------------------------------------------------------------------
# POST /sponsor-companies — register company
# ---------------------------------------------------------------------------

class TestRegisterCompany:
    def test_register_returns_503_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.post(
            "/sponsor-companies",
            json={
                "name": "Test Sponsor Co",
                "contact_email": "test@example.com",
            },
        )
        assert resp.status_code == 503

    def test_register_missing_name(self):
        """Rejects missing name field."""
        resp = client.post(
            "/sponsor-companies",
            json={"contact_email": "test@example.com"},
        )
        assert resp.status_code == 422

    def test_register_missing_email(self):
        """Rejects missing contact_email field."""
        resp = client.post(
            "/sponsor-companies",
            json={"name": "Test Sponsor Co"},
        )
        assert resp.status_code == 422

    def test_register_empty_name(self):
        """Rejects empty name (min_length=1)."""
        resp = client.post(
            "/sponsor-companies",
            json={"name": "", "contact_email": "test@example.com"},
        )
        assert resp.status_code == 422

    def test_register_no_body(self):
        """Rejects request with no body."""
        resp = client.post("/sponsor-companies")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /sponsor-companies/{company_id} — get company profile
# ---------------------------------------------------------------------------

class TestGetCompany:
    def test_get_company_invalid_uuid(self):
        """Rejects invalid UUID format."""
        resp = client.get("/sponsor-companies/not-a-valid-uuid")
        assert resp.status_code == 400

    def test_get_company_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.get(f"/sponsor-companies/{VALID_UUID}")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# PATCH /sponsor-companies/{company_id} — update company
# ---------------------------------------------------------------------------

class TestUpdateCompany:
    def test_update_invalid_uuid(self):
        """Rejects invalid company_id format."""
        resp = client.patch(
            "/sponsor-companies/not-a-valid-uuid",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 400

    def test_update_no_fields(self):
        """Rejects update with no fields to change."""
        resp = client.patch(
            f"/sponsor-companies/{VALID_UUID}",
            json={},
        )
        assert resp.status_code == 400

    def test_update_no_db(self):
        """Returns 503 when DB pool is unavailable (after validation passes)."""
        resp = client.patch(
            f"/sponsor-companies/{VALID_UUID}",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# DELETE /sponsor-companies/{company_id} — delete company
# ---------------------------------------------------------------------------

class TestDeleteCompany:
    def test_delete_invalid_uuid(self):
        """Rejects invalid company_id format."""
        resp = client.delete("/sponsor-companies/not-a-valid-uuid")
        assert resp.status_code == 400

    def test_delete_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.delete(f"/sponsor-companies/{VALID_UUID}")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /sponsor-companies/{company_id}/create-event-checkout — Stripe checkout
# ---------------------------------------------------------------------------

class TestCreateEventCheckout:
    def test_checkout_invalid_uuid(self):
        """Rejects invalid company_id format."""
        resp = client.post(
            "/sponsor-companies/not-a-valid-uuid/create-event-checkout",
            json={
                "tier": "featured",
                "event_title": "Test Event",
                "event_kind": "meetup",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 400

    def test_checkout_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-checkout",
            json={
                "tier": "featured",
                "event_title": "Test Event",
                "event_kind": "meetup",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 503

    def test_checkout_invalid_tier(self):
        """Rejects invalid tier value."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-checkout",
            json={
                "tier": "mega_ultra",
                "event_title": "Test Event",
                "event_kind": "meetup",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 422

    def test_checkout_invalid_event_kind(self):
        """Rejects invalid event_kind value."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-checkout",
            json={
                "tier": "featured",
                "event_title": "Test Event",
                "event_kind": "invalid_kind",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 422

    def test_checkout_missing_required_fields(self):
        """Rejects request missing required fields."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-checkout",
            json={},
        )
        assert resp.status_code == 422

    def test_checkout_invalid_date_format(self):
        """Rejects invalid date format."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-checkout",
            json={
                "tier": "featured",
                "event_title": "Test Event",
                "event_kind": "meetup",
                "event_date": "June 1st 2026",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /sponsor-companies/{company_id}/create-event-demo — demo bypass
# ---------------------------------------------------------------------------

class TestCreateEventDemo:
    def test_demo_invalid_uuid(self):
        """Rejects invalid company_id format."""
        resp = client.post(
            "/sponsor-companies/not-a-valid-uuid/create-event-demo",
            json={
                "tier": "featured",
                "event_title": "Test Event",
                "event_kind": "meetup",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 400

    def test_demo_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-demo",
            json={
                "tier": "featured",
                "event_title": "Demo Event",
                "event_kind": "meetup",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 503

    def test_demo_missing_fields(self):
        """Rejects demo request with missing required fields."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-demo",
            json={},
        )
        assert resp.status_code == 422

    def test_demo_invalid_kind(self):
        """Rejects demo request with invalid event_kind."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-event-demo",
            json={
                "tier": "featured",
                "event_title": "Demo Event",
                "event_kind": "bad_kind",
                "event_date": "2026-06-01",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /sponsor-companies/{company_id}/create-subscription-checkout
# ---------------------------------------------------------------------------

class TestCreateSubscriptionCheckout:
    def test_subscription_invalid_uuid(self):
        """Rejects invalid company_id format."""
        resp = client.post(
            "/sponsor-companies/not-a-valid-uuid/create-subscription-checkout",
            json={"tier": "featured"},
        )
        assert resp.status_code == 400

    def test_subscription_invalid_tier(self):
        """Rejects invalid tier value."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-subscription-checkout",
            json={"tier": "mega_ultra"},
        )
        assert resp.status_code == 422

    def test_subscription_no_body(self):
        """Rejects request with no body."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-subscription-checkout",
        )
        assert resp.status_code == 422

    def test_subscription_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.post(
            f"/sponsor-companies/{VALID_UUID}/create-subscription-checkout",
            json={"tier": "featured"},
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# PATCH validation: disallowed columns
# ---------------------------------------------------------------------------

class TestUpdateCompanyValidation:
    def test_update_disallowed_column(self):
        """Rejects update with disallowed column."""
        resp = client.patch(
            f"/sponsor-companies/{VALID_UUID}",
            json={"admin_user_id": "hacker"},
        )
        assert resp.status_code == 400

    def test_update_valid_fields_no_db(self):
        """Valid fields but no DB returns 503."""
        resp = client.patch(
            f"/sponsor-companies/{VALID_UUID}",
            json={"name": "New Name", "description": "New desc"},
        )
        assert resp.status_code == 503
