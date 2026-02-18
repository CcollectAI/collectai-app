"""Tests for the beta signup router (pre-launch email collection)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    # Reset rate-limit state between tests
    from app.routes.beta_signup_router import _RATE_LIMIT

    _RATE_LIMIT.clear()
    from main import app

    return TestClient(app, raise_server_exceptions=False)


def _make_mock_pool(*, execute_side_effect=None, fetchval_return=0, fetch_return=None):
    """Create a mock asyncpg pool."""
    pool = AsyncMock()
    pool.execute = AsyncMock(side_effect=execute_side_effect)
    pool.fetchval = AsyncMock(return_value=fetchval_return)
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    return pool


# ---------------------------------------------------------------------------
# POST /api/beta-signup — validation
# ---------------------------------------------------------------------------


class TestBetaSignupValidation:
    """POST /api/beta-signup — request validation."""

    def test_missing_email_returns_422(self, client):
        """Missing email field → 422."""
        resp = client.post("/api/beta-signup", json={})
        assert resp.status_code == 422

    def test_empty_email_returns_422(self, client):
        """Empty string email → 422."""
        resp = client.post("/api/beta-signup", json={"email": "   "})
        assert resp.status_code == 422

    def test_invalid_email_no_at_returns_422(self, client):
        """Email without @ → 422."""
        resp = client.post("/api/beta-signup", json={"email": "notanemail"})
        assert resp.status_code == 422

    def test_invalid_email_no_domain_returns_422(self, client):
        """Email without domain → 422."""
        resp = client.post("/api/beta-signup", json={"email": "user@"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/beta-signup — success / error cases
# ---------------------------------------------------------------------------


class TestBetaSignupEndpoint:
    """POST /api/beta-signup — functional tests."""

    def test_valid_signup_returns_200(self, client):
        """Valid email with mocked DB → 200."""
        mock_pool = _make_mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=mock_pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "test@example.com"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "You're on the list!"
        assert data["email"] == "test@example.com"
        mock_pool.execute.assert_awaited_once()

    def test_valid_signup_with_referral(self, client):
        """Optional referral_source is accepted."""
        mock_pool = _make_mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=mock_pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "ref@example.com", "referral_source": "twitter"},
            )
        assert resp.status_code == 200
        # Verify referral was passed to the query
        call_args = mock_pool.execute.call_args
        assert call_args[0][2] == "twitter"

    def test_duplicate_email_returns_409(self, client):
        """Duplicate email → 409."""
        exc = Exception("duplicate key value violates unique constraint")
        mock_pool = _make_mock_pool(execute_side_effect=exc)
        with patch("app.routes.beta_signup_router.get_pool", return_value=mock_pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "dupe@example.com"},
            )
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"]["message"].lower()

    def test_no_pool_returns_503(self, client):
        """No DB pool → 503."""
        with patch("app.routes.beta_signup_router.get_pool", return_value=None):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "nopool@example.com"},
            )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /ops/beta-signups
# ---------------------------------------------------------------------------


class TestListBetaSignups:
    """GET /ops/beta-signups — ops-key protected listing."""

    def test_list_empty_no_db(self, client):
        """No DB pool → graceful empty response."""
        with patch("app.routes.beta_signup_router.get_pool", return_value=None):
            resp = client.get(
                "/ops/beta-signups",
                headers={"X-Ops-Key": "test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["signups"] == []
        assert data["total"] == 0

    def test_list_with_data(self, client):
        """Returns mocked signup rows."""
        now = datetime.now(timezone.utc)
        mock_rows = [
            {
                "id": uuid.uuid4(),
                "email": "a@example.com",
                "referral_source": "google",
                "ip_address": "1.2.3.4",
                "signed_up_at": now,
            },
            {
                "id": uuid.uuid4(),
                "email": "b@example.com",
                "referral_source": None,
                "ip_address": "5.6.7.8",
                "signed_up_at": now,
            },
        ]
        mock_pool = _make_mock_pool(fetchval_return=2, fetch_return=mock_rows)
        with patch("app.routes.beta_signup_router.get_pool", return_value=mock_pool):
            resp = client.get(
                "/ops/beta-signups",
                headers={"X-Ops-Key": "test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["signups"]) == 2
        assert data["signups"][0]["email"] == "a@example.com"

    def test_pagination_params(self, client):
        """Query params page/per_page are accepted."""
        mock_pool = _make_mock_pool(fetchval_return=0)
        with patch("app.routes.beta_signup_router.get_pool", return_value=mock_pool):
            resp = client.get(
                "/ops/beta-signups?page=2&per_page=10",
                headers={"X-Ops-Key": "test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["per_page"] == 10
