"""Tests for the MFA router."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestMFAStatus:
    """GET /auth/mfa/status."""

    def test_returns_not_enrolled_without_supabase(self, client):
        """Without Supabase admin client, returns enrolled=false."""
        with patch("app.routes.mfa_router._get_supabase_admin", return_value=None):
            resp = client.get("/auth/mfa/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enrolled"] is False
            assert data["factors"] == []

    def test_v1_alias(self, client):
        """GET /v1/auth/mfa/status also works."""
        with patch("app.routes.mfa_router._get_supabase_admin", return_value=None):
            resp = client.get("/v1/auth/mfa/status")
            assert resp.status_code == 200

    def test_returns_enrolled_when_verified_factor(self, client):
        """Returns enrolled=true when a verified TOTP factor exists."""
        mock_admin = MagicMock()
        factor = MagicMock()
        factor.id = "factor-123"
        factor.friendly_name = "My Phone"
        factor.status = "verified"
        mock_admin.auth.admin.mfa_list_factors.return_value = MagicMock(totp=[factor])

        with patch("app.routes.mfa_router._get_supabase_admin", return_value=mock_admin):
            resp = client.get("/auth/mfa/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enrolled"] is True
            assert len(data["factors"]) == 1
            assert data["factors"][0]["id"] == "factor-123"

    def test_returns_not_enrolled_when_unverified_factor(self, client):
        """Returns enrolled=false when factor exists but is unverified."""
        mock_admin = MagicMock()
        factor = MagicMock()
        factor.id = "factor-456"
        factor.friendly_name = None
        factor.status = "unverified"
        mock_admin.auth.admin.mfa_list_factors.return_value = MagicMock(totp=[factor])

        with patch("app.routes.mfa_router._get_supabase_admin", return_value=mock_admin):
            resp = client.get("/auth/mfa/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enrolled"] is False


class TestMFAUnenroll:
    """POST /auth/mfa/unenroll."""

    def test_unenroll_not_available(self, client):
        """Without Supabase admin client, returns 503."""
        with patch("app.routes.mfa_router._get_supabase_admin", return_value=None):
            resp = client.post("/auth/mfa/unenroll", json={"factor_id": "f-123"})
            assert resp.status_code == 503

    def test_unenroll_missing_factor_id(self, client):
        """Missing factor_id returns 400."""
        mock_admin = MagicMock()
        with patch("app.routes.mfa_router._get_supabase_admin", return_value=mock_admin):
            resp = client.post("/auth/mfa/unenroll", json={})
            assert resp.status_code == 400

    def test_unenroll_success(self, client):
        """Successful unenroll returns success=true."""
        mock_admin = MagicMock()
        mock_admin.auth.admin.mfa_delete_factor.return_value = None

        with patch("app.routes.mfa_router._get_supabase_admin", return_value=mock_admin):
            resp = client.post("/auth/mfa/unenroll", json={"factor_id": "f-123"})
            assert resp.status_code == 200
            assert resp.json()["success"] is True
