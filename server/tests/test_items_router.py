"""Tests for app/routes/items_router.py — Item CRUD + batch operations.

Covers:
  - POST /items — create item (in-memory fallback + DB mock)
  - GET  /items — list items (in-memory fallback)
  - POST /items/batch-archive — batch archive (in-memory fallback)
  - POST /items/batch-delete — batch delete (in-memory fallback)
  - PATCH /items/{item_id}/attributes — update attributes (DB mock)
  - Validation: missing name, empty body

The items router has an in-memory fallback (DB_ENABLED=false), so most tests
work without DB mocking. DB-path tests use mocked get_db_pool().
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
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from app.routes.items_router import _DEMO_ITEMS  # noqa: E402

client = TestClient(app)

TEST_USER_ID = "items-test-user-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool():
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=None)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool, mock_conn


def _auth_override():
    from app.auth import get_current_user_id

    async def _fake_user():
        return TEST_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_demo_items():
    _DEMO_ITEMS.clear()
    yield
    _DEMO_ITEMS.clear()


# ---------------------------------------------------------------------------
# Tests: POST /items — Create item (in-memory fallback)
# ---------------------------------------------------------------------------

class TestCreateItem:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_create_item_success(self):
        """Create an item using in-memory fallback."""
        resp = client.post("/items", json={
            "name": "Charizard Base Set",
            "category": "pokemon",
            "notes": "Holo 1st edition",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Charizard Base Set"
        assert data["category"] == "pokemon"
        assert data["id"].startswith("demo-")

    def test_create_item_minimal_fields(self):
        """Only name is required."""
        resp = client.post("/items", json={"name": "Test Item"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Item"
        assert data["category"] is None
        assert data["notes"] is None

    def test_create_item_with_estimated_value(self):
        resp = client.post("/items", json={
            "name": "Rare Card",
            "estimated_value": 999.99,
        })
        assert resp.status_code == 200
        assert resp.json()["estimated_value"] == 999.99

    def test_create_item_no_name_fails(self):
        """Name is required; omitting it should return 422."""
        resp = client.post("/items", json={"category": "pokemon"})
        assert resp.status_code == 422

    def test_create_item_empty_body_fails(self):
        resp = client.post("/items", json={})
        assert resp.status_code == 422

    @patch("app.routes.items_router.get_db_pool")
    def test_create_item_db_path(self, mock_get_pool):
        """When DB pool is available, item is created in the database."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(return_value=None)

        resp = client.post("/items", json={
            "name": "DB Item",
            "category": "mtg",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "DB Item"
        # ID should be a proper UUID (not demo-*)
        assert not data["id"].startswith("demo-")

    @patch("app.routes.items_router.get_db_pool")
    def test_create_item_db_error(self, mock_get_pool):
        """DB error during creation returns 500."""
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.execute = AsyncMock(side_effect=Exception("DB connection lost"))

        resp = client.post("/items", json={"name": "Failing Item"})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Tests: GET /items — List items (in-memory fallback)
# ---------------------------------------------------------------------------

class TestListItems:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_list_empty(self):
        resp = client.get("/items")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["has_more"] is False
        assert body["next_cursor"] is None

    def test_list_after_create(self):
        """Items created via POST are visible in GET."""
        client.post("/items", json={"name": "Item A"})
        client.post("/items", json={"name": "Item B"})

        resp = client.get("/items")
        assert resp.status_code == 200
        body = resp.json()
        data = body["items"]
        assert len(data) == 2
        names = [item["name"] for item in data]
        assert "Item A" in names
        assert "Item B" in names


# ---------------------------------------------------------------------------
# Tests: POST /items/batch-archive — Batch archive (in-memory fallback)
# ---------------------------------------------------------------------------

class TestBatchArchive:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_batch_archive_success(self):
        """Archive existing items from in-memory store."""
        # Create items first
        r1 = client.post("/items", json={"name": "Archive 1"}).json()
        r2 = client.post("/items", json={"name": "Archive 2"}).json()
        client.post("/items", json={"name": "Keep This"})

        resp = client.post("/items/batch-archive", json={
            "item_ids": [r1["id"], r2["id"]],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["affected_count"] == 2

        # Verify only 1 item remains
        remaining = client.get("/items").json()["items"]
        assert len(remaining) == 1
        assert remaining[0]["name"] == "Keep This"

    def test_batch_archive_empty_ids_fails(self):
        """item_ids must have at least 1 entry."""
        resp = client.post("/items/batch-archive", json={"item_ids": []})
        assert resp.status_code == 422

    def test_batch_archive_nonexistent_ids(self):
        """Archiving non-existent IDs affects 0 items."""
        resp = client.post("/items/batch-archive", json={
            "item_ids": ["nonexistent-id-1", "nonexistent-id-2"],
        })
        assert resp.status_code == 200
        assert resp.json()["affected_count"] == 0


# ---------------------------------------------------------------------------
# Tests: POST /items/batch-delete — Batch delete (in-memory fallback)
# ---------------------------------------------------------------------------

class TestBatchDelete:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_batch_delete_success(self):
        r1 = client.post("/items", json={"name": "Delete 1"}).json()
        r2 = client.post("/items", json={"name": "Delete 2"}).json()
        client.post("/items", json={"name": "Survivor"})

        resp = client.post("/items/batch-delete", json={
            "item_ids": [r1["id"], r2["id"]],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["affected_count"] == 2

        remaining = client.get("/items").json()["items"]
        assert len(remaining) == 1

    def test_batch_delete_empty_ids_fails(self):
        resp = client.post("/items/batch-delete", json={"item_ids": []})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: PATCH /items/{item_id}/attributes — Update attributes (DB path)
# ---------------------------------------------------------------------------

class TestUpdateItemAttributes:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_update_attributes_offline_noop(self):
        """When pool is None, returns ok without error."""
        resp = client.patch("/items/some-item-id/attributes", json={
            "attributes": {"color": "blue"},
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_update_attributes_empty_payload(self):
        """Empty attributes + no size fields returns ok immediately."""
        resp = client.patch("/items/some-item-id/attributes", json={
            "attributes": {},
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @patch("app.routes.items_router.get_db_pool")
    def test_update_attributes_db_path(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        resp = client.patch("/items/some-item-id/attributes", json={
            "attributes": {"year": 1999},
            "item_size": "10cm",
            "size_system": "cm",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # Verify the DB was called
        conn.execute.assert_awaited_once()
