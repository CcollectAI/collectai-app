"""Tests for the seed-user management router and pipeline."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    os.environ.setdefault("DEV_MODE", "true")
    os.environ.setdefault("DB_ENABLED", "false")
    from main import app
    return TestClient(app, raise_server_exceptions=False)


# ── Persona data ──────────────────────────────────────────────────────────


class TestPersonas:
    """Validate the static persona definitions."""

    def test_eight_personas(self):
        from pipelines.seed_beta_users import PERSONAS
        assert len(PERSONAS) == 8

    def test_unique_emails(self):
        from pipelines.seed_beta_users import PERSONAS
        emails = [p.email for p in PERSONAS]
        assert len(set(emails)) == 8

    def test_unique_handles(self):
        from pipelines.seed_beta_users import PERSONAS
        handles = [p.handle for p in PERSONAS]
        assert len(set(handles)) == 8

    def test_all_emails_use_test_tld(self):
        from pipelines.seed_beta_users import PERSONAS
        for p in PERSONAS:
            assert p.email.endswith("@collectai.test"), f"{p.email} must use .test TLD"

    def test_every_persona_has_items(self):
        from pipelines.seed_beta_users import PERSONAS
        for p in PERSONAS:
            assert len(p.items) >= 2, f"{p.handle} needs at least 2 items"
            assert len(p.items) <= 5, f"{p.handle} has more than 5 items"

    def test_valid_locales(self):
        from pipelines.seed_beta_users import PERSONAS
        valid = {"en-US", "de-DE", "ja-JP", "nl-NL"}
        for p in PERSONAS:
            assert p.locale in valid, f"{p.handle} has invalid locale {p.locale}"

    def test_valid_currencies(self):
        from pipelines.seed_beta_users import PERSONAS
        valid = {"EUR", "USD", "JPY", "GBP"}
        for p in PERSONAS:
            assert p.currency in valid, f"{p.handle} has invalid currency {p.currency}"

    def test_valid_regions(self):
        from pipelines.seed_beta_users import PERSONAS
        valid = {"americas", "europe", "japan", "other"}
        for p in PERSONAS:
            assert p.region in valid, f"{p.handle} has invalid region {p.region}"


# ── Dry-run ───────────────────────────────────────────────────────────────


class TestDryRun:
    """seed_users(dry_run=True) should produce a summary without side effects."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_summary(self):
        from pipelines.seed_beta_users import seed_users
        result = await seed_users(dry_run=True)
        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["total"] == 8
        assert len(result["users"]) == 8

    @pytest.mark.asyncio
    async def test_dry_run_user_ids_are_none(self):
        from pipelines.seed_beta_users import seed_users
        result = await seed_users(dry_run=True)
        for u in result["users"]:
            assert u["user_id"] is None


# ── Seed without infra ───────────────────────────────────────────────────


class TestSeedNoInfra:
    """seed_users() without Supabase/DB should fail gracefully."""

    @pytest.mark.asyncio
    async def test_no_supabase_returns_error(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            from pipelines.seed_beta_users import seed_users
            result = await seed_users(dry_run=False)
            assert result["success"] is False
            assert result["error"] == "supabase_unavailable"

    @pytest.mark.asyncio
    async def test_no_dsn_returns_error(self):
        # Provide supabase but no DB_DSN
        mock_admin = MagicMock()
        with (
            patch("pipelines.seed_beta_users._get_supabase_admin", return_value=mock_admin),
            patch.dict(os.environ, {"DB_DSN": ""}),
        ):
            from pipelines.seed_beta_users import seed_users
            result = await seed_users(dry_run=False)
            assert result["success"] is False
            assert result["error"] == "no_dsn"


# ── Cleanup without infra ────────────────────────────────────────────────


class TestCleanupNoInfra:
    """cleanup_seed_users() without Supabase should fail gracefully."""

    @pytest.mark.asyncio
    async def test_no_supabase_returns_error(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            from pipelines.seed_beta_users import cleanup_seed_users
            result = await cleanup_seed_users()
            assert result["success"] is False
            assert result["deleted"] == 0


# ── Router endpoints ─────────────────────────────────────────────────────


class TestSeedEndpoint:
    """POST /ops/seed-users."""

    def test_dry_run_via_endpoint(self, client):
        resp = client.post("/ops/seed-users?dry_run=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["dry_run"] is True
        assert data["total"] == 8

    def test_requires_ops_key_in_prod(self, client):
        import app.auth as auth_mod
        orig_dev, orig_key = auth_mod.DEV_MODE, auth_mod.OPS_API_KEY
        try:
            auth_mod.DEV_MODE = False
            auth_mod.OPS_API_KEY = "test-key-123"

            resp = client.post("/ops/seed-users?dry_run=true")
            assert resp.status_code == 401

            resp = client.post(
                "/ops/seed-users?dry_run=true",
                headers={"X-Ops-Key": "test-key-123"},
            )
            assert resp.status_code == 200
        finally:
            auth_mod.DEV_MODE = orig_dev
            auth_mod.OPS_API_KEY = orig_key


class TestDeleteEndpoint:
    """DELETE /ops/seed-users."""

    def test_delete_no_supabase(self, client):
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}):
            resp = client.delete("/ops/seed-users")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert data["deleted"] == 0


# ── Cleanup table ordering ───────────────────────────────────────────────


class TestCleanupOrder:
    """Verify cleanup tables are in correct dependency order."""

    def test_items_before_profiles(self):
        from pipelines.seed_beta_users import _CLEANUP_TABLES
        items_idx = _CLEANUP_TABLES.index("items")
        profiles_idx = _CLEANUP_TABLES.index("profiles")
        assert items_idx < profiles_idx, "items must be deleted before profiles"

    def test_mandate_deals_first(self):
        from pipelines.seed_beta_users import _CLEANUP_TABLES
        assert _CLEANUP_TABLES[0] == "mandate_deals"

    def test_user_public_profiles_last(self):
        from pipelines.seed_beta_users import _CLEANUP_TABLES
        assert _CLEANUP_TABLES[-1] == "user_public_profiles"
