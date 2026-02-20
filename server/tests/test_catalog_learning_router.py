"""Tests for app/features/catalog_learning_router.py.

Covers user suggestion endpoint and admin ops endpoints.
DB_ENABLED=false and DEV_MODE=true so auth is bypassed and no real DB is needed.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    os.environ["DEV_MODE"] = "true"
    os.environ["DB_ENABLED"] = "false"
    os.environ["CATALOG_LEARNING_ENABLED"] = "true"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["PER_USER_RATE_LIMIT_ENABLED"] = "false"
    from main import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _suggestion_payload(**overrides):
    defaults = {
        "source": "barcode",
        "input_data": {"barcode": "9780141036144"},
        "suggested_name": "1984 by George Orwell",
        "suggested_category": "manga",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# POST /catalog/suggest — user endpoint
# ===========================================================================


class TestSubmitSuggestion:
    """POST /catalog/suggest."""

    def test_returns_503_when_no_db(self, client):
        """No DB pool -> 503."""
        resp = client.post("/catalog/suggest", json=_suggestion_payload())
        # Without a DB pool, returns 503
        assert resp.status_code == 503

    @patch("app.features.catalog_learning_router.CATALOG_LEARNING_ENABLED", True)
    @patch("app.features.catalog_learning_router.get_pool")
    def test_happy_path_creates_suggestion(self, mock_pool, client):
        """Valid payload + DB -> 201 with suggestion_id."""
        suggestion_id = str(uuid4())
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value=None)  # no existing dupe
        pool.execute = AsyncMock()
        mock_pool.return_value = pool

        resp = client.post("/catalog/suggest", json=_suggestion_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["matched_existing"] is False
        assert "id" in data

    @patch("app.features.catalog_learning_router.CATALOG_LEARNING_ENABLED", True)
    @patch("app.features.catalog_learning_router.get_pool")
    def test_duplicate_returns_existing(self, mock_pool, client):
        """Duplicate submission returns existing suggestion."""
        existing_id = str(uuid4())
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"id": existing_id, "status": "pending"})
        mock_pool.return_value = pool

        resp = client.post("/catalog/suggest", json=_suggestion_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == existing_id
        assert data["matched_existing"] is True

    def test_validation_rejects_invalid_source(self, client):
        """Invalid source field -> 422."""
        payload = _suggestion_payload(source="invalid_source")
        resp = client.post("/catalog/suggest", json=payload)
        assert resp.status_code == 422

    def test_validation_rejects_empty_name(self, client):
        """Empty suggested_name -> 422."""
        payload = _suggestion_payload(suggested_name="")
        resp = client.post("/catalog/suggest", json=payload)
        assert resp.status_code == 422

    def test_validation_accepts_all_sources(self, client):
        """All four valid sources pass validation (will 503 without DB)."""
        for source in ("barcode", "photo", "manual", "url"):
            payload = _suggestion_payload(source=source)
            resp = client.post("/catalog/suggest", json=payload)
            # 503 is expected (no DB), not 422 (validation error)
            assert resp.status_code == 503


# ===========================================================================
# GET /ops/catalog-suggestions — admin endpoint
# ===========================================================================


class TestListSuggestions:
    """GET /ops/catalog-suggestions."""

    def test_returns_empty_when_no_db(self, client):
        """No DB pool -> empty list."""
        resp = client.get("/ops/catalog-suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == []
        assert data["total"] == 0

    @patch("app.features.catalog_learning_router.get_pool")
    def test_returns_suggestions_from_db(self, mock_pool, client):
        """With DB, returns paginated results."""
        from datetime import datetime, timezone

        pool = MagicMock()
        pool.fetchval = AsyncMock(return_value=1)
        pool.fetch = AsyncMock(side_effect=[
            # Main query
            [{
                "id": uuid4(),
                "user_id": uuid4(),
                "source": "barcode",
                "suggested_name": "Test Item",
                "suggested_category": "pokemon",
                "matched_category": None,
                "confidence": 0.0,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
            }],
            # Aggregation query
            [{"name": "test item", "cnt": 3, "users": 2}],
        ])
        mock_pool.return_value = pool

        resp = client.get("/ops/catalog-suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["suggested_name"] == "Test Item"
        assert len(data["aggregation"]) == 1


# ===========================================================================
# POST /ops/catalog-suggestions/{id}/action
# ===========================================================================


class TestSuggestionAction:
    """POST /ops/catalog-suggestions/{id}/action."""

    @patch("app.features.catalog_learning_router.get_pool")
    def test_approve_updates_status(self, mock_pool, client):
        sid = str(uuid4())
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"id": sid, "status": "pending"})
        pool.execute = AsyncMock()
        mock_pool.return_value = pool

        resp = client.post(
            f"/ops/catalog-suggestions/{sid}/action",
            json={"action": "approve", "mapped_category": "pokemon"},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "approve"

    @patch("app.features.catalog_learning_router.get_pool")
    def test_reject_updates_status(self, mock_pool, client):
        sid = str(uuid4())
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"id": sid, "status": "pending"})
        pool.execute = AsyncMock()
        mock_pool.return_value = pool

        resp = client.post(
            f"/ops/catalog-suggestions/{sid}/action",
            json={"action": "reject"},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "reject"

    @patch("app.features.catalog_learning_router.get_pool")
    def test_map_requires_category(self, mock_pool, client):
        sid = str(uuid4())
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={"id": sid, "status": "pending"})
        mock_pool.return_value = pool

        resp = client.post(
            f"/ops/catalog-suggestions/{sid}/action",
            json={"action": "map"},
        )
        assert resp.status_code == 400

    @patch("app.features.catalog_learning_router.get_pool")
    def test_404_for_missing_suggestion(self, mock_pool, client):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value=None)
        mock_pool.return_value = pool

        resp = client.post(
            f"/ops/catalog-suggestions/{uuid4()}/action",
            json={"action": "approve"},
        )
        assert resp.status_code == 404


# ===========================================================================
# GET /ops/category-candidates
# ===========================================================================


class TestListCandidates:
    """GET /ops/category-candidates."""

    def test_returns_empty_when_no_db(self, client):
        resp = client.get("/ops/category-candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidates"] == []
        assert data["total"] == 0
