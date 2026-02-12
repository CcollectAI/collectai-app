"""Tests for app/routes/user_settings_router.py — user preferences CRUD.

Covers:
  - GET  /settings — defaults when no DB row, stored values, offline fallback,
    asyncpg.PostgresError handling
  - PUT  /settings — valid upsert, invalid currency/region/locale,
    missing fields, partial update, offline mode

All tests mock _get_db_pool() and override the auth dependency so no real
database or JWT is needed.
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

TEST_USER_ID = "user-settings-test-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool(fetchrow_return=None, fetchrow_side_effect=None):
    """Create a mock asyncpg pool with a mock connection context manager."""
    mock_conn = AsyncMock()
    if fetchrow_side_effect is not None:
        mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    else:
        mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    mock_pool = MagicMock()
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = mock_acquire
    return mock_pool, mock_conn


# ===========================================================================
# GET /settings — offline mode (no DB pool, default)
# ===========================================================================

class TestGetSettingsOffline:
    """When _get_db_pool() returns None, GET should return defaults."""

    def test_returns_defaults_when_pool_unavailable(self):
        """GET /settings with no DB pool returns EUR/europe/de-DE."""
        r = client.get("/settings")
        assert r.status_code == 200
        data = r.json()
        assert data["currency"] == "EUR"
        assert data["region"] == "europe"
        assert data["locale"] == "de-DE"


# ===========================================================================
# GET /settings — with mocked DB pool
# ===========================================================================

class TestGetSettingsWithDB:
    """GET /settings when a DB pool is available."""

    def test_returns_defaults_when_no_row_exists(self):
        """If no user_settings row exists, return defaults."""
        mock_pool, _conn = _mock_pool(fetchrow_return=None)
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.get("/settings")
        assert r.status_code == 200
        data = r.json()
        assert data["currency"] == "EUR"
        assert data["region"] == "europe"
        assert data["locale"] == "de-DE"

    def test_returns_stored_values_when_row_exists(self):
        """If a user_settings row exists, return its values."""
        stored = {"currency": "USD", "region": "americas", "locale": "en-US"}
        mock_pool, _conn = _mock_pool(fetchrow_return=stored)
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.get("/settings")
        assert r.status_code == 200
        data = r.json()
        assert data["currency"] == "USD"
        assert data["region"] == "americas"
        assert data["locale"] == "en-US"

    def test_returns_stored_jpy_japan(self):
        """Verify non-default stored values (JPY / japan / ja-JP) round-trip."""
        stored = {"currency": "JPY", "region": "japan", "locale": "ja-JP"}
        mock_pool, _conn = _mock_pool(fetchrow_return=stored)
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.get("/settings")
        assert r.status_code == 200
        data = r.json()
        assert data["currency"] == "JPY"
        assert data["region"] == "japan"
        assert data["locale"] == "ja-JP"

    def test_handles_postgres_error_with_500(self):
        """asyncpg.PostgresError during fetch should return 500."""
        mock_pool, _conn = _mock_pool(
            fetchrow_side_effect=asyncpg.PostgresError("connection lost"),
        )
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.get("/settings")
        assert r.status_code == 500
        detail = r.json()["detail"]
        # error_response wraps detail in a dict with "detail" and "code" keys
        if isinstance(detail, dict):
            assert detail["code"] == "DB_ERROR"
        else:
            assert "settings" in detail.lower() or "failed" in detail.lower()


# ===========================================================================
# PUT /settings — validation errors (no DB needed)
# ===========================================================================

class TestPutSettingsValidation:
    """PUT /settings validation: invalid currency/region/locale/empty body."""

    def test_invalid_currency_returns_400(self):
        r = client.put("/settings", json={"currency": "FAKE"})
        assert r.status_code == 400
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail["code"] == "VALIDATION_ERROR"
            assert "currency" in detail["detail"].lower()

    def test_invalid_region_returns_400(self):
        r = client.put("/settings", json={"region": "antarctica"})
        assert r.status_code == 400
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail["code"] == "VALIDATION_ERROR"
            assert "region" in detail["detail"].lower()

    def test_invalid_locale_returns_400(self):
        r = client.put("/settings", json={"locale": "xx-XX"})
        assert r.status_code == 400
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail["code"] == "VALIDATION_ERROR"
            assert "locale" in detail["detail"].lower()

    def test_no_fields_returns_400(self):
        """PUT with all-null fields (empty object) should return 400."""
        r = client.put("/settings", json={})
        assert r.status_code == 400
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert "at least one" in detail["detail"].lower()


# ===========================================================================
# PUT /settings — offline mode (no DB pool)
# ===========================================================================

class TestPutSettingsOffline:
    """PUT /settings when _get_db_pool() returns None (offline mode)."""

    def test_offline_returns_merged_defaults(self):
        """Submitted values merged with defaults, success=True."""
        r = client.put("/settings", json={"currency": "GBP"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        settings = data["settings"]
        assert settings["currency"] == "GBP"
        assert settings["region"] == "europe"   # default
        assert settings["locale"] == "de-DE"    # default

    def test_offline_all_fields_provided(self):
        r = client.put("/settings", json={
            "currency": "JPY",
            "region": "japan",
            "locale": "ja-JP",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["settings"]["currency"] == "JPY"
        assert data["settings"]["region"] == "japan"
        assert data["settings"]["locale"] == "ja-JP"


# ===========================================================================
# PUT /settings — with mocked DB pool
# ===========================================================================

class TestPutSettingsWithDB:
    """PUT /settings with a DB pool: upsert and partial update behaviour."""

    def test_upsert_valid_currency_region_locale(self):
        """Full upsert with all three fields returns the upserted row."""
        returned_row = {"currency": "USD", "region": "americas", "locale": "en-US"}
        mock_pool, mock_conn = _mock_pool(fetchrow_return=returned_row)
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.put("/settings", json={
                "currency": "USD",
                "region": "americas",
                "locale": "en-US",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["settings"]["currency"] == "USD"
        assert data["settings"]["region"] == "americas"
        assert data["settings"]["locale"] == "en-US"

        # Verify the SQL was an INSERT ... ON CONFLICT (upsert)
        sql = mock_conn.fetchrow.call_args[0][0]
        assert "INSERT INTO user_settings" in sql
        assert "ON CONFLICT" in sql

    def test_partial_update_preserves_existing(self):
        """When only currency is provided, region/locale come from COALESCE
        on the DB side. The returned row should reflect the merge."""
        # The DB returns the merged row (existing region/locale preserved)
        returned_row = {"currency": "GBP", "region": "europe", "locale": "de-DE"}
        mock_pool, mock_conn = _mock_pool(fetchrow_return=returned_row)
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.put("/settings", json={"currency": "GBP"})
        assert r.status_code == 200
        data = r.json()
        assert data["settings"]["currency"] == "GBP"
        assert data["settings"]["region"] == "europe"
        assert data["settings"]["locale"] == "de-DE"

        # Verify COALESCE is used in SQL so NULL params preserve existing
        sql = mock_conn.fetchrow.call_args[0][0]
        assert "COALESCE" in sql

    def test_db_error_on_put_returns_500(self):
        """asyncpg.PostgresError during upsert should return 500."""
        mock_pool, _conn = _mock_pool(
            fetchrow_side_effect=asyncpg.PostgresError("disk full"),
        )
        with patch("app.routes.user_settings_router._get_db_pool", return_value=mock_pool):
            r = client.put("/settings", json={"currency": "EUR"})
        assert r.status_code == 500
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail["code"] == "DB_ERROR"
