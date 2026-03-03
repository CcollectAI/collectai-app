"""
Tests for app/features/taxonomy_router.py — taxonomy registry endpoints.

Covers:
  - GET /taxonomy/current     — current taxonomy (in-memory fallback + cached + DB)
  - GET /taxonomy/versions    — all versions (in-memory fallback + DB)
  - GET /taxonomy/categories  — flat category list (in-memory fallback + cached + DB)
  - GET /taxonomy/{version}   — specific version detail (no-DB 503 + DB happy/404)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn_ctx():
    """Create a mock async context manager for get_conn()."""
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, ctx


def _make_taxonomy_row(version="v2.0", categories=None, mapping_rules=None,
                       effective_from=None, deprecated_at=None,
                       migration_from=None, migration_rules=None,
                       notes="Production taxonomy", created_by="admin"):
    """Create a mock asyncpg Record for taxonomy_registry."""
    row = MagicMock()
    data = {
        "version": version,
        "categories": categories or [
            {"category_id": "pokemon", "display_name": "Pokemon", "subtypes": [{"id": "tcg"}]},
            {"category_id": "lego", "display_name": "LEGO", "subtypes": [], "collections": ["star_wars"]},
        ],
        "mapping_rules": mapping_rules or [{"from": "old_cat", "to": "new_cat"}],
        "effective_from": effective_from or NOW,
        "deprecated_at": deprecated_at,
        "migration_from": migration_from,
        "migration_rules": migration_rules,
        "notes": notes,
        "created_by": created_by,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


def _make_version_row(version="v2.0", deprecated_at=None, migration_from=None,
                      notes="Production", created_by="admin"):
    """Create a mock asyncpg Record for the versions list query."""
    row = MagicMock()
    data = {
        "version": version,
        "effective_from": NOW,
        "deprecated_at": deprecated_at,
        "migration_from": migration_from,
        "notes": notes,
        "created_by": created_by,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


def _clear_taxonomy_cache():
    """Clear taxonomy-related cache entries to ensure test isolation."""
    from app.cache import cache_delete
    cache_delete("taxonomy:current")
    cache_delete("taxonomy:categories")


# ===========================================================================
# GET /taxonomy/current — in-memory fallback (DB_ENABLED=false)
# ===========================================================================


class TestTaxonomyCurrentInMemory:
    """Tests for GET /taxonomy/current when DB is disabled."""

    def test_returns_fallback_taxonomy(self):
        """Fallback taxonomy returned when DB is not configured."""
        _clear_taxonomy_cache()
        resp = client.get("/taxonomy/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1.0"
        assert isinstance(data["categories"], list)
        assert data["mapping_rules_count"] == 0
        assert data["effective_from"] is None
        assert "Fallback" in data["notes"]

    def test_fallback_categories_have_correct_structure(self):
        """Each fallback category has category_id and display_name."""
        _clear_taxonomy_cache()
        resp = client.get("/taxonomy/current")
        cats = resp.json()["categories"]
        assert len(cats) > 0
        for cat in cats:
            assert "category_id" in cat
            assert "display_name" in cat
            assert isinstance(cat["category_id"], str)
            assert isinstance(cat["display_name"], str)

    def test_fallback_includes_known_categories(self):
        """Verify some known categories are present in fallback."""
        _clear_taxonomy_cache()
        resp = client.get("/taxonomy/current")
        cat_ids = [c["category_id"] for c in resp.json()["categories"]]
        assert "pokemon" in cat_ids
        assert "lego" in cat_ids
        assert "funko" in cat_ids
        assert "mtg" in cat_ids


# ===========================================================================
# GET /taxonomy/current — mocked DB
# ===========================================================================


class TestTaxonomyCurrentMockedDB:
    """Tests for GET /taxonomy/current with mocked database."""

    def test_happy_path_from_db(self):
        """Returns taxonomy from DB with correct structure."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row())

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/current")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v2.0"
        assert len(data["categories"]) == 2
        assert data["mapping_rules_count"] == 1
        assert data["notes"] == "Production taxonomy"

    def test_cache_miss_header(self):
        """First DB fetch returns X-Cache: MISS."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row())

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/current")

        assert resp.headers.get("x-cache") == "MISS"
        assert "max-age=3600" in resp.headers.get("cache-control", "")

    def test_cache_hit_header(self):
        """Second call returns X-Cache: HIT from cache."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row())

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            # First call populates cache
            client.get("/taxonomy/current")

        # Second call — no patches needed, should come from cache
        resp = client.get("/taxonomy/current")
        assert resp.status_code == 200
        assert resp.headers.get("x-cache") == "HIT"
        _clear_taxonomy_cache()

    def test_no_db_row_returns_fallback(self):
        """When DB returns no rows, falls back to default taxonomy."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/current")

        assert resp.status_code == 200
        assert resp.json()["version"] == "v1.0"
        assert "Fallback" in resp.json()["notes"]

    def test_db_exception_returns_fallback(self):
        """When DB raises an exception, gracefully falls back."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("connection lost"))

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/current")

        assert resp.status_code == 200
        assert resp.json()["version"] == "v1.0"


# ===========================================================================
# GET /taxonomy/versions — in-memory fallback
# ===========================================================================


class TestTaxonomyVersionsInMemory:
    """Tests for GET /taxonomy/versions when DB is disabled."""

    def test_returns_fallback_version_list(self):
        """Fallback returns single v1.0 version."""
        resp = client.get("/taxonomy/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert len(data["versions"]) == 1
        assert data["versions"][0]["version"] == "v1.0"
        assert data["versions"][0]["status"] == "active"


# ===========================================================================
# GET /taxonomy/versions — mocked DB
# ===========================================================================


class TestTaxonomyVersionsMockedDB:
    """Tests for GET /taxonomy/versions with mocked database."""

    def test_happy_path_multiple_versions(self):
        """Returns multiple versions with correct status flags."""
        conn, ctx = _mock_conn_ctx()
        active_row = _make_version_row("v2.0")
        deprecated_row = _make_version_row("v1.0", deprecated_at=NOW)
        conn.fetch = AsyncMock(return_value=[active_row, deprecated_row])

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/versions")

        assert resp.status_code == 200
        versions = resp.json()["versions"]
        assert len(versions) == 2
        assert versions[0]["version"] == "v2.0"
        assert versions[0]["status"] == "active"
        assert versions[1]["version"] == "v1.0"
        assert versions[1]["status"] == "deprecated"

    def test_version_entry_schema(self):
        """Each version entry has the expected fields."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[_make_version_row()])

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/versions")

        v = resp.json()["versions"][0]
        assert "version" in v
        assert "effective_from" in v
        assert "deprecated_at" in v
        assert "status" in v
        assert "migration_from" in v
        assert "notes" in v
        assert "created_by" in v

    def test_empty_versions_from_db(self):
        """When DB returns no versions, returns empty list."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/versions")

        assert resp.status_code == 200
        assert resp.json()["versions"] == []

    def test_db_exception_returns_fallback(self):
        """When DB raises an exception, gracefully returns fallback."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(side_effect=RuntimeError("connection lost"))

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/versions")

        assert resp.status_code == 200
        assert resp.json()["versions"][0]["version"] == "v1.0"


# ===========================================================================
# GET /taxonomy/categories — in-memory fallback
# ===========================================================================


class TestTaxonomyCategoriesInMemory:
    """Tests for GET /taxonomy/categories when DB is disabled."""

    def test_returns_fallback_category_list(self):
        """Fallback returns flat category list."""
        _clear_taxonomy_cache()
        resp = client.get("/taxonomy/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1.0"
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) > 0

    def test_fallback_category_structure(self):
        """Each fallback category has required fields for UI dropdowns."""
        _clear_taxonomy_cache()
        resp = client.get("/taxonomy/categories")
        cats = resp.json()["categories"]
        for cat in cats:
            assert "category_id" in cat
            assert "display_name" in cat
            assert "subtypes" in cat
            assert "collections" in cat
            assert isinstance(cat["subtypes"], list)
            assert isinstance(cat["collections"], list)


# ===========================================================================
# GET /taxonomy/categories — mocked DB
# ===========================================================================


class TestTaxonomyCategoriesMockedDB:
    """Tests for GET /taxonomy/categories with mocked database."""

    def test_happy_path_from_db(self):
        """Returns flat category list from DB taxonomy."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row())

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/categories")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v2.0"
        cats = data["categories"]
        assert len(cats) == 2
        # Verify flat structure
        assert cats[0]["category_id"] == "pokemon"
        assert cats[0]["display_name"] == "Pokemon"
        assert cats[0]["subtypes"] == ["tcg"]
        _clear_taxonomy_cache()

    def test_cache_miss_then_hit(self):
        """First call is MISS, second is HIT."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row())

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp1 = client.get("/taxonomy/categories")

        assert resp1.headers.get("x-cache") == "MISS"

        resp2 = client.get("/taxonomy/categories")
        assert resp2.headers.get("x-cache") == "HIT"
        assert resp2.json()["version"] == "v2.0"
        _clear_taxonomy_cache()

    def test_no_db_row_returns_fallback(self):
        """When DB has no current taxonomy, falls back."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/categories")

        assert resp.status_code == 200
        assert resp.json()["version"] == "v1.0"

    def test_empty_categories_returns_fallback(self):
        """When DB row has null categories, falls back."""
        _clear_taxonomy_cache()
        conn, ctx = _mock_conn_ctx()
        row = _make_taxonomy_row(categories=None)
        # Override categories to be explicitly None/empty
        row_data = {"version": "v2.0", "categories": None}
        row.__getitem__ = lambda self, key: row_data[key]
        conn.fetchrow = AsyncMock(return_value=row)

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/categories")

        assert resp.status_code == 200
        assert resp.json()["version"] == "v1.0"


# ===========================================================================
# GET /taxonomy/{version} — specific version (no DB = 503)
# ===========================================================================


class TestTaxonomyByVersionInMemory:
    """Tests for GET /taxonomy/{version} when DB is disabled."""

    def test_returns_503_when_db_disabled(self):
        """Specific version lookup requires DB — returns 503."""
        resp = client.get("/taxonomy/v2.0")
        assert resp.status_code == 503


# ===========================================================================
# GET /taxonomy/{version} — specific version (mocked DB)
# ===========================================================================


class TestTaxonomyByVersionMockedDB:
    """Tests for GET /taxonomy/{version} with mocked database."""

    def test_happy_path(self):
        """Returns full taxonomy version detail."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row(
            version="v2.0",
            migration_from="v1.0",
            migration_rules=[{"rule": "rename old_cat to new_cat"}],
        ))

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/v2.0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v2.0"
        assert isinstance(data["categories"], list)
        assert isinstance(data["mapping_rules"], list)
        assert data["migration_from"] == "v1.0"
        assert data["notes"] == "Production taxonomy"
        assert data["created_by"] == "admin"

    def test_version_not_found_returns_404(self):
        """When version doesn't exist, returns 404."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/v99.0")

        assert resp.status_code == 404

    def test_response_schema(self):
        """Verify all expected fields are present in version detail."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row())

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/v2.0")

        data = resp.json()
        expected_keys = {"version", "categories", "mapping_rules",
                         "effective_from", "deprecated_at", "migration_from",
                         "migration_rules", "notes", "created_by"}
        assert expected_keys.issubset(data.keys())

    def test_deprecated_version(self):
        """Returns deprecated version with deprecated_at field set."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_taxonomy_row(
            version="v1.0",
            deprecated_at=NOW,
        ))

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/v1.0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deprecated_at"] is not None

    def test_db_exception_returns_500(self):
        """When DB raises an exception, returns 500."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("connection lost"))

        with patch("app.features.taxonomy_router.db_configured", return_value=True), \
             patch("app.features.taxonomy_router.get_conn", return_value=ctx):
            resp = client.get("/taxonomy/v2.0")

        assert resp.status_code == 500
