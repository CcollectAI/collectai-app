"""Tests for app/routes/beta_signup_router.py — Beta email signup + admin listing.

Covers:
  - POST /api/beta-signup — valid signup, duplicate handling, invalid email, missing fields
  - GET  /ops/beta-signups — paginated listing (ops-key protected, DEV_MODE bypasses)
  - Rate limiting behavior (in-memory per-IP)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("FORCE_DEV_MODE", "true")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PER_USER_RATE_LIMIT_ENABLED"] = "false"

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool(*, execute_side_effect=None, fetchval_return=0, fetch_return=None):
    """Create a mock asyncpg pool with configurable behaviour."""
    pool = MagicMock()
    pool.execute = AsyncMock(side_effect=execute_side_effect)
    pool.fetchval = AsyncMock(return_value=fetchval_return)
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    return pool


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Reset the in-memory rate limiter between tests."""
    from app.routes.beta_signup_router import _RATE_LIMIT
    _RATE_LIMIT.clear()
    yield
    _RATE_LIMIT.clear()


# ---------------------------------------------------------------------------
# POST /api/beta-signup — valid signup
# ---------------------------------------------------------------------------

class TestBetaSignupValid:
    def test_valid_email_signup(self):
        """A valid email should be accepted and echoed back."""
        pool = _mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "Alice@Example.COM"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "You're on the list!"
        # Email should be lowercased
        assert body["email"] == "alice@example.com"
        pool.execute.assert_awaited_once()

    def test_signup_with_referral_source(self):
        """Optional referral_source should be passed to DB."""
        pool = _mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "user@test.io", "referral_source": "twitter"},
            )
        assert resp.status_code == 200
        # Verify referral source was passed to execute
        call_args = pool.execute.call_args
        assert call_args[0][2] == "twitter"  # $2 = referral_source

    def test_signup_email_trimmed(self):
        """Leading/trailing whitespace should be stripped from email."""
        pool = _mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "  padded@example.com  "},
            )
        assert resp.status_code == 200
        assert resp.json()["email"] == "padded@example.com"


# ---------------------------------------------------------------------------
# POST /api/beta-signup — duplicate handling
# ---------------------------------------------------------------------------

class TestBetaSignupDuplicate:
    def test_duplicate_email_returns_409(self):
        """Re-signing up with the same email should return 409."""
        pool = _mock_pool(
            execute_side_effect=Exception("duplicate key value violates unique constraint"),
        )
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "dup@test.com"},
            )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "already" in detail["message"].lower()

    def test_unique_violation_detected(self):
        """Unique violation detection covers 'unique' keyword."""
        pool = _mock_pool(
            execute_side_effect=Exception("UniqueViolationError: email unique"),
        )
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "unique@test.com"},
            )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/beta-signup — invalid email
# ---------------------------------------------------------------------------

class TestBetaSignupInvalidEmail:
    def test_missing_at_sign(self):
        """Email without @ should fail validation (422)."""
        resp = client.post("/api/beta-signup", json={"email": "not-an-email"})
        assert resp.status_code == 422

    def test_missing_tld(self):
        """Email without TLD should fail validation."""
        resp = client.post("/api/beta-signup", json={"email": "user@host"})
        assert resp.status_code == 422

    def test_empty_email(self):
        """Empty string email should fail validation."""
        resp = client.post("/api/beta-signup", json={"email": ""})
        assert resp.status_code == 422

    def test_missing_email_field(self):
        """Request body without email field should fail validation."""
        resp = client.post("/api/beta-signup", json={})
        assert resp.status_code == 422

    def test_empty_body(self):
        """Completely empty body should return 422."""
        resp = client.post("/api/beta-signup", content=b"", headers={"content-type": "application/json"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/beta-signup — rate limiting
# ---------------------------------------------------------------------------

class TestBetaSignupRateLimit:
    def test_rate_limit_after_max_attempts(self):
        """After 5 signups from same IP, the 6th should be rate-limited."""
        pool = _mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            for i in range(5):
                resp = client.post(
                    "/api/beta-signup",
                    json={"email": f"user{i}@rate.test"},
                )
                assert resp.status_code == 200, f"Request {i} should succeed"

            # 6th should be blocked
            resp = client.post(
                "/api/beta-signup",
                json={"email": "user5@rate.test"},
            )
            assert resp.status_code == 429

    def test_rate_limit_independent_per_ip(self):
        """Different IPs should have independent limits."""
        pool = _mock_pool()
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            # First IP — 5 requests
            for i in range(5):
                resp = client.post(
                    "/api/beta-signup",
                    json={"email": f"a{i}@test.com"},
                    headers={"x-forwarded-for": "1.1.1.1"},
                )
                assert resp.status_code == 200

            # Second IP — should still work
            resp = client.post(
                "/api/beta-signup",
                json={"email": "b0@test.com"},
                headers={"x-forwarded-for": "2.2.2.2"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/beta-signup — DB unavailable
# ---------------------------------------------------------------------------

class TestBetaSignupDBDown:
    def test_no_pool_returns_503(self):
        """When DB pool is None, return 503."""
        with patch("app.routes.beta_signup_router.get_pool", return_value=None):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "down@test.com"},
            )
        assert resp.status_code == 503

    def test_unexpected_db_error_returns_500(self):
        """Non-duplicate DB errors should return 500."""
        pool = _mock_pool(
            execute_side_effect=Exception("connection refused"),
        )
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.post(
                "/api/beta-signup",
                json={"email": "err@test.com"},
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /ops/beta-signups — paginated listing
# ---------------------------------------------------------------------------

class TestListBetaSignups:
    def test_empty_list(self):
        """Should return empty list when no signups exist."""
        pool = _mock_pool(fetchval_return=0, fetch_return=[])
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.get("/ops/beta-signups")
        assert resp.status_code == 200
        body = resp.json()
        assert body["signups"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    def test_pagination_params(self):
        """Custom page/per_page should be respected."""
        pool = _mock_pool(fetchval_return=0, fetch_return=[])
        with patch("app.routes.beta_signup_router.get_pool", return_value=pool):
            resp = client.get("/ops/beta-signups?page=2&per_page=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["per_page"] == 10

    def test_invalid_page_zero(self):
        """page=0 should fail validation (ge=1)."""
        resp = client.get("/ops/beta-signups?page=0")
        assert resp.status_code == 422

    def test_per_page_too_large(self):
        """per_page > 200 should fail validation (le=200)."""
        resp = client.get("/ops/beta-signups?per_page=999")
        assert resp.status_code == 422

    def test_no_pool_returns_empty(self):
        """When DB pool is None, return empty list (not an error)."""
        with patch("app.routes.beta_signup_router.get_pool", return_value=None):
            resp = client.get("/ops/beta-signups")
        assert resp.status_code == 200
        body = resp.json()
        assert body["signups"] == []
        assert body["total"] == 0
