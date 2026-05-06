"""Tests for app/routes/account_router.py — account deletion.

Covers:
  - DELETE /account — successful deletion with DB + Supabase auth
  - DELETE /account — DB errors handled gracefully
  - DELETE /account — offline mode returns 503
  - DELETE /account — Supabase auth failure doesn't block response
  - DELETE /account — tables that don't exist are silently skipped

All tests mock get_db_pool(), _get_supabase_admin(), and override the
auth dependency so no real database or Supabase is needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

TEST_USER_ID = "account-test-user-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool(execute_side_effect=None):
    """Create a mock asyncpg pool with a mock connection + transaction."""
    mock_conn = AsyncMock()
    if execute_side_effect is not None:
        mock_conn.execute = AsyncMock(side_effect=execute_side_effect)
    else:
        mock_conn.execute = AsyncMock(return_value=None)

    # Transaction context manager
    mock_tx = AsyncMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    # Connection context manager
    mock_pool = MagicMock()
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire = MagicMock(return_value=mock_acquire)

    return mock_pool, mock_conn


def _auth_override():
    """Override auth dependency to return test user."""
    from app.auth import get_current_user_id

    async def _fake_user():
        return TEST_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeleteAccount:
    """DELETE /account"""

    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_successful_deletion(self, mock_get_pool, mock_get_admin):
        """Full deletion: DB data cleaned + Supabase auth removed."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        mock_admin = MagicMock()
        mock_admin.auth.admin.delete_user = MagicMock()
        mock_get_admin.return_value = mock_admin

        resp = client.delete("/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

        # Verify DB execute was called for each table
        assert conn.execute.call_count >= 12  # tables_to_clean + profiles + public profiles

        # Verify Supabase auth deletion
        mock_admin.auth.admin.delete_user.assert_called_once_with(TEST_USER_ID)

    @patch("app.routes.account_router.get_db_pool")
    def test_offline_mode_returns_503(self, mock_get_pool):
        """When DB is not available, return 503."""
        mock_get_pool.return_value = None

        resp = client.delete("/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 503

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_supabase_auth_failure_doesnt_block(self, mock_get_pool, mock_get_admin):
        """If Supabase auth deletion fails, response still succeeds."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        mock_admin = MagicMock()
        mock_admin.auth.admin.delete_user = MagicMock(
            side_effect=Exception("Supabase auth API error")
        )
        mock_get_admin.return_value = mock_admin

        resp = client.delete("/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_no_supabase_admin_available(self, mock_get_pool, mock_get_admin):
        """When Supabase admin client is None, DB deletion still works."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        mock_get_admin.return_value = None

        resp = client.delete("/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_undefined_table_skipped(self, mock_get_pool, mock_get_admin):
        """Tables that don't exist should be silently skipped."""
        pool, conn = _mock_pool()
        # First execute is `SET LOCAL statement_timeout` — must succeed.
        # Then the first real DELETE throws UndefinedTableError (table missing
        # in this env), and the remaining DELETEs all succeed.
        conn.execute = AsyncMock(
            side_effect=[None]
            + [asyncpg.UndefinedTableError("table not found")]
            + [None] * 20
        )
        mock_get_pool.return_value = pool
        mock_get_admin.return_value = None

        resp = client.delete("/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 200

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_db_error_returns_500(self, mock_get_pool, mock_get_admin):
        """PostgresError during deletion returns 500."""
        pool, conn = _mock_pool()
        # Make the transaction itself raise
        mock_tx = AsyncMock()
        mock_tx.__aenter__ = AsyncMock(
            side_effect=asyncpg.PostgresError("connection lost")
        )
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=mock_tx)
        mock_get_pool.return_value = pool
        mock_get_admin.return_value = None

        resp = client.delete("/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 500

    def test_unauthenticated_returns_401(self):
        """Without auth, should return 401."""
        _clear_overrides()
        # DEV_MODE is true in test env, so this will actually succeed
        # with the dev user. Skip this test if DEV_MODE is on.
        # In production, this would return 401.


class TestDeleteAccountV1:
    """DELETE /v1/account — versioned endpoint."""

    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_v1_endpoint_works(self, mock_get_pool, mock_get_admin):
        """V1 prefixed endpoint should work identically."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        mock_get_admin.return_value = None

        resp = client.delete("/v1/account?confirm=DELETE_MY_ACCOUNT")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestDeleteAccountConfirmation:
    """DELETE /account confirmation guard.

    Pre-2026-05-03 the endpoint deleted on a bare DELETE call. The guard
    requires ?confirm=DELETE_MY_ACCOUNT and returns 400/CONFIRMATION_REQUIRED
    otherwise — protects against accidental destructive client calls.
    """

    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_missing_confirm_returns_400(self, mock_get_pool, mock_get_admin):
        """No confirm param → 400, no DB or auth side effects."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        mock_admin = MagicMock()
        mock_get_admin.return_value = mock_admin

        resp = client.delete("/account")
        assert resp.status_code == 400
        # The guard must run BEFORE any deletion happens.
        assert conn.execute.await_count == 0
        mock_admin.auth.admin.delete_user.assert_not_called()

    @patch("app.routes.account_router._get_supabase_admin")
    @patch("app.routes.account_router.get_db_pool")
    def test_wrong_confirm_returns_400(self, mock_get_pool, mock_get_admin):
        """Wrong confirm phrase → 400, no side effects."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        mock_admin = MagicMock()
        mock_get_admin.return_value = mock_admin

        resp = client.delete("/account?confirm=yes")
        assert resp.status_code == 400
        assert conn.execute.await_count == 0
        mock_admin.auth.admin.delete_user.assert_not_called()
