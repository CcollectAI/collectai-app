"""
Tests for app/features/set_router.py — set/collection completion tracking.

Covers:
  - GET  /sets                    — list sets (in-memory fallback + DB path)
  - GET  /sets/{set_id}           — set detail (in-memory + DB happy/404/invalid UUID)
  - GET  /sets/{set_id}/progress  — user progress (in-memory + DB happy/404/no-progress)
  - PUT  /sets/{set_id}/progress  — update progress (DB add/remove, validation, 503)
  - GET  /sets/my-progress        — list tracked sets (in-memory + DB path)
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

SET_ID = str(uuid4())
SET_ID_2 = str(uuid4())
ITEM_ID_A = str(uuid4())
ITEM_ID_B = str(uuid4())
ITEM_ID_C = str(uuid4())
USER_ID = "dev-user-local"
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


def _make_set_row(set_id=SET_ID, category_id="pokemon", name="Base Set",
                  total_items=102, description="Original Base Set",
                  metadata=None):
    """Create a dict that looks like an asyncpg Record for sets."""
    row = MagicMock()
    data = {
        "id": set_id,
        "category_id": category_id,
        "name": name,
        "description": description,
        "total_items": total_items,
        "release_date": NOW,
        "image_url": "https://example.com/set.jpg",
        "external_id": "base-set-001",
        "metadata": metadata or "{}",
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


def _make_item_row(item_id=ITEM_ID_A, set_id=SET_ID, name="Charizard",
                   position=1, rarity="rare", metadata=None):
    """Create a dict that looks like an asyncpg Record for set_items."""
    row = MagicMock()
    data = {
        "id": item_id,
        "set_id": set_id,
        "name": name,
        "position": position,
        "external_id": "item-001",
        "image_url": "https://example.com/item.jpg",
        "rarity": rarity,
        "metadata": metadata or "{}",
        "created_at": NOW,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


def _make_progress_row(user_id=USER_ID, set_id=SET_ID, owned_item_ids=None,
                       owned_count=2, completion_pct=50.0, notes="halfway"):
    """Create a mock asyncpg Record for user_set_progress."""
    row = MagicMock()
    data = {
        "user_id": user_id,
        "set_id": set_id,
        "owned_item_ids": owned_item_ids or [ITEM_ID_A, ITEM_ID_B],
        "owned_count": owned_count,
        "completion_pct": completion_pct,
        "notes": notes,
        "updated_at": NOW,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


def _make_my_progress_row(set_id=SET_ID, set_name="Base Set",
                          category_id="pokemon", total_items=102,
                          owned_count=50, completion_pct=49.02):
    """Create a mock asyncpg Record for the my-progress JOIN query."""
    row = MagicMock()
    data = {
        "set_id": set_id,
        "set_name": set_name,
        "category_id": category_id,
        "total_items": total_items,
        "image_url": "https://example.com/set.jpg",
        "owned_count": owned_count,
        "completion_pct": completion_pct,
        "notes": "tracking",
        "updated_at": NOW,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.get = lambda key, default=None: data.get(key, default)
    return row


# ===========================================================================
# GET /sets — list sets (in-memory fallback)
# ===========================================================================


class TestListSetsInMemory:
    """Tests for GET /sets when DB is disabled (DB_ENABLED=false)."""

    def test_returns_empty_list(self):
        """In-memory fallback returns empty sets list."""
        resp = client.get("/sets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sets"] == []
        assert data["total"] == 0

    def test_response_schema(self):
        """Verify response has required keys with correct types."""
        resp = client.get("/sets")
        data = resp.json()
        assert isinstance(data["sets"], list)
        assert isinstance(data["total"], int)

    def test_with_category_filter(self):
        """Passing category_id still returns empty in in-memory mode."""
        resp = client.get("/sets?category_id=pokemon")
        assert resp.status_code == 200
        assert resp.json()["sets"] == []

    def test_with_pagination_params(self):
        """Pagination params are accepted without error."""
        resp = client.get("/sets?limit=10&offset=5")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ===========================================================================
# GET /sets — list sets (mocked DB)
# ===========================================================================


class TestListSetsMockedDB:
    """Tests for GET /sets with mocked database."""

    def test_happy_path_no_filter(self):
        """Returns all sets without category filter."""
        conn, ctx = _mock_conn_ctx()
        row1 = _make_set_row(SET_ID, "pokemon", "Base Set")
        row2 = _make_set_row(SET_ID_2, "mtg", "Alpha")
        conn.fetch = AsyncMock(return_value=[row1, row2])
        conn.fetchval = AsyncMock(return_value=2)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["sets"]) == 2
        assert data["sets"][0]["name"] == "Base Set"
        assert data["sets"][1]["name"] == "Alpha"

    def test_happy_path_with_category_filter(self):
        """Returns sets filtered by category_id."""
        conn, ctx = _mock_conn_ctx()
        row = _make_set_row(SET_ID, "pokemon", "Base Set")
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchval = AsyncMock(return_value=1)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets?category_id=pokemon")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["sets"][0]["category_id"] == "pokemon"

    def test_empty_db_result(self):
        """When DB returns no rows, returns empty list with total 0."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets")

        assert resp.status_code == 200
        assert resp.json()["sets"] == []
        assert resp.json()["total"] == 0

    def test_set_summary_schema(self):
        """Each set summary has the expected fields and types."""
        conn, ctx = _mock_conn_ctx()
        row = _make_set_row()
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchval = AsyncMock(return_value=1)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets")

        s = resp.json()["sets"][0]
        assert isinstance(s["id"], str)
        assert isinstance(s["category_id"], str)
        assert isinstance(s["name"], str)
        assert isinstance(s["total_items"], int)
        assert isinstance(s["metadata"], dict)
        # Optional fields
        assert "description" in s
        assert "release_date" in s
        assert "image_url" in s
        assert "external_id" in s
        assert "created_at" in s
        assert "updated_at" in s

    def test_metadata_string_parsed_to_dict(self):
        """Metadata stored as JSON string is parsed to dict."""
        conn, ctx = _mock_conn_ctx()
        row = _make_set_row(metadata='{"theme": "water"}')
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchval = AsyncMock(return_value=1)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets")

        assert resp.json()["sets"][0]["metadata"] == {"theme": "water"}


# ===========================================================================
# GET /sets/{set_id} — set detail (in-memory fallback)
# ===========================================================================


class TestGetSetDetailInMemory:
    """Tests for GET /sets/{set_id} when DB is disabled."""

    def test_returns_404_when_db_disabled(self):
        """In-memory mode always returns 404 for set detail."""
        resp = client.get(f"/sets/{SET_ID}")
        assert resp.status_code == 404

    def test_invalid_uuid_returns_400(self):
        """Invalid UUID format returns 400 before DB check."""
        resp = client.get("/sets/not-a-uuid")
        assert resp.status_code == 400


# ===========================================================================
# GET /sets/{set_id} — set detail (mocked DB)
# ===========================================================================


class TestGetSetDetailMockedDB:
    """Tests for GET /sets/{set_id} with mocked database."""

    def test_happy_path_with_items(self):
        """Returns set detail with items list."""
        conn, ctx = _mock_conn_ctx()
        set_row = _make_set_row()
        item_row_a = _make_item_row(ITEM_ID_A, SET_ID, "Charizard", 1)
        item_row_b = _make_item_row(ITEM_ID_B, SET_ID, "Blastoise", 2)
        conn.fetchrow = AsyncMock(return_value=set_row)
        conn.fetch = AsyncMock(return_value=[item_row_a, item_row_b])

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == SET_ID
        assert data["name"] == "Base Set"
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Charizard"
        assert data["items"][1]["name"] == "Blastoise"

    def test_set_not_found_returns_404(self):
        """When set doesn't exist in DB, returns 404."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}")

        assert resp.status_code == 404

    def test_set_with_no_items(self):
        """Set exists but has no items — items list is empty."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_set_row(total_items=0))
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}")

        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_item_schema(self):
        """Each set item has the expected fields."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=_make_set_row())
        conn.fetch = AsyncMock(return_value=[_make_item_row()])

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}")

        item = resp.json()["items"][0]
        assert isinstance(item["id"], str)
        assert isinstance(item["set_id"], str)
        assert isinstance(item["name"], str)
        assert "position" in item
        assert "rarity" in item
        assert isinstance(item["metadata"], dict)


# ===========================================================================
# GET /sets/{set_id}/progress — user progress (in-memory fallback)
# ===========================================================================


class TestGetProgressInMemory:
    """Tests for GET /sets/{set_id}/progress when DB is disabled."""

    def test_returns_empty_progress(self):
        """In-memory mode returns zero-progress response."""
        resp = client.get(f"/sets/{SET_ID}/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == USER_ID
        assert data["set_id"] == SET_ID
        assert data["owned_item_ids"] == []
        assert data["owned_count"] == 0
        assert data["completion_pct"] == 0.0
        assert data["notes"] is None
        assert data["updated_at"] is None

    def test_progress_response_schema(self):
        """All required ProgressResponse fields are present."""
        resp = client.get(f"/sets/{SET_ID}/progress")
        data = resp.json()
        required_keys = {"user_id", "set_id", "owned_item_ids", "owned_count",
                         "completion_pct", "notes", "updated_at"}
        assert required_keys.issubset(data.keys())

    def test_invalid_uuid_returns_400(self):
        """Invalid set_id UUID returns 400."""
        resp = client.get("/sets/bad-uuid/progress")
        assert resp.status_code == 400


# ===========================================================================
# GET /sets/{set_id}/progress — user progress (mocked DB)
# ===========================================================================


class TestGetProgressMockedDB:
    """Tests for GET /sets/{set_id}/progress with mocked database."""

    def test_happy_path_with_progress(self):
        """When user has progress tracked, returns full progress data."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=True)  # set exists
        conn.fetchrow = AsyncMock(return_value=_make_progress_row())

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}/progress")

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == USER_ID
        assert data["set_id"] == SET_ID
        assert data["owned_count"] == 2
        assert data["completion_pct"] == 50.0
        assert data["notes"] == "halfway"
        assert len(data["owned_item_ids"]) == 2

    def test_set_not_found_returns_404(self):
        """When set does not exist, returns 404."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=False)  # set does not exist

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}/progress")

        assert resp.status_code == 404

    def test_no_progress_returns_empty(self):
        """When set exists but user has no progress, returns zeroed-out response."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=True)  # set exists
        conn.fetchrow = AsyncMock(return_value=None)  # no progress row

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get(f"/sets/{SET_ID}/progress")

        assert resp.status_code == 200
        data = resp.json()
        assert data["owned_count"] == 0
        assert data["completion_pct"] == 0.0
        assert data["owned_item_ids"] == []


# ===========================================================================
# PUT /sets/{set_id}/progress — update progress (in-memory fallback)
# ===========================================================================


class TestUpdateProgressInMemory:
    """Tests for PUT /sets/{set_id}/progress when DB is disabled."""

    def test_returns_503_when_db_disabled(self):
        """DB required for updates — returns 503 when disabled."""
        resp = client.put(
            f"/sets/{SET_ID}/progress",
            json={"item_ids": [ITEM_ID_A], "action": "add"},
        )
        assert resp.status_code == 503

    def test_invalid_set_uuid_returns_400(self):
        """Invalid set_id UUID returns 400 before DB check."""
        resp = client.put(
            "/sets/bad-uuid/progress",
            json={"item_ids": [ITEM_ID_A], "action": "add"},
        )
        assert resp.status_code == 400

    def test_invalid_item_uuid_returns_400(self):
        """Invalid item_id UUID in the body returns 400."""
        resp = client.put(
            f"/sets/{SET_ID}/progress",
            json={"item_ids": ["not-a-uuid"], "action": "add"},
        )
        assert resp.status_code in (400, 503)  # UUID validated before DB check

    def test_invalid_action_returns_422(self):
        """Action must be 'add' or 'remove'; anything else is 422."""
        resp = client.put(
            f"/sets/{SET_ID}/progress",
            json={"item_ids": [ITEM_ID_A], "action": "delete"},
        )
        assert resp.status_code == 422

    def test_empty_item_ids_returns_422(self):
        """Empty item_ids list violates min_length=1."""
        resp = client.put(
            f"/sets/{SET_ID}/progress",
            json={"item_ids": [], "action": "add"},
        )
        assert resp.status_code == 422

    def test_missing_action_returns_422(self):
        """Missing action field triggers 422."""
        resp = client.put(
            f"/sets/{SET_ID}/progress",
            json={"item_ids": [ITEM_ID_A]},
        )
        assert resp.status_code == 422

    def test_missing_item_ids_returns_422(self):
        """Missing item_ids field triggers 422."""
        resp = client.put(
            f"/sets/{SET_ID}/progress",
            json={"action": "add"},
        )
        assert resp.status_code == 422


# ===========================================================================
# PUT /sets/{set_id}/progress — update progress (mocked DB)
# ===========================================================================


class TestUpdateProgressMockedDB:
    """Tests for PUT /sets/{set_id}/progress with mocked database."""

    def test_add_items_happy_path(self):
        """Adding items returns updated progress."""
        conn, ctx = _mock_conn_ctx()
        # set exists with 10 items
        set_row = MagicMock()
        set_data = {"id": SET_ID, "total_items": 10}
        set_row.__getitem__ = lambda self, key: set_data[key]
        conn.fetchrow = AsyncMock(side_effect=[
            set_row,  # SELECT set
            MagicMock(  # RETURNING row
                __getitem__=lambda self, key: {
                    "owned_item_ids": [ITEM_ID_A],
                    "owned_count": 1,
                    "completion_pct": 10.0,
                }[key],
            ),
        ])
        conn.fetchval = AsyncMock(return_value=1)  # valid_count == len(item_ids)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.put(
                f"/sets/{SET_ID}/progress",
                json={"item_ids": [ITEM_ID_A], "action": "add"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == USER_ID
        assert data["set_id"] == SET_ID
        assert data["owned_count"] == 1
        assert data["completion_pct"] == 10.0
        assert ITEM_ID_A in data["owned_item_ids"]

    def test_remove_items_happy_path(self):
        """Removing items returns updated progress."""
        conn, ctx = _mock_conn_ctx()
        set_row = MagicMock()
        set_data = {"id": SET_ID, "total_items": 10}
        set_row.__getitem__ = lambda self, key: set_data[key]
        conn.fetchrow = AsyncMock(side_effect=[
            set_row,  # SELECT set
            MagicMock(  # RETURNING row
                __getitem__=lambda self, key: {
                    "owned_item_ids": [],
                    "owned_count": 0,
                    "completion_pct": 0.0,
                }[key],
            ),
        ])
        conn.fetchval = AsyncMock(return_value=1)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.put(
                f"/sets/{SET_ID}/progress",
                json={"item_ids": [ITEM_ID_A], "action": "remove"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["owned_count"] == 0
        assert data["owned_item_ids"] == []

    def test_set_not_found_returns_404(self):
        """When set doesn't exist, returns 404."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value=None)  # set not found

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.put(
                f"/sets/{SET_ID}/progress",
                json={"item_ids": [ITEM_ID_A], "action": "add"},
            )

        assert resp.status_code == 404

    def test_invalid_item_ids_not_in_set_returns_400(self):
        """When item_ids don't belong to the set, returns 400."""
        conn, ctx = _mock_conn_ctx()
        set_row = MagicMock()
        set_data = {"id": SET_ID, "total_items": 10}
        set_row.__getitem__ = lambda self, key: set_data[key]
        conn.fetchrow = AsyncMock(return_value=set_row)
        # valid_count is 0 while we sent 1 item_id
        conn.fetchval = AsyncMock(return_value=0)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.put(
                f"/sets/{SET_ID}/progress",
                json={"item_ids": [ITEM_ID_A], "action": "add"},
            )

        assert resp.status_code == 400

    def test_multiple_items_add(self):
        """Adding multiple items at once succeeds."""
        conn, ctx = _mock_conn_ctx()
        set_row = MagicMock()
        set_data = {"id": SET_ID, "total_items": 10}
        set_row.__getitem__ = lambda self, key: set_data[key]
        conn.fetchrow = AsyncMock(side_effect=[
            set_row,
            MagicMock(
                __getitem__=lambda self, key: {
                    "owned_item_ids": [ITEM_ID_A, ITEM_ID_B],
                    "owned_count": 2,
                    "completion_pct": 20.0,
                }[key],
            ),
        ])
        conn.fetchval = AsyncMock(return_value=2)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.put(
                f"/sets/{SET_ID}/progress",
                json={"item_ids": [ITEM_ID_A, ITEM_ID_B], "action": "add"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["owned_count"] == 2
        assert len(data["owned_item_ids"]) == 2


# ===========================================================================
# GET /sets/my-progress — my tracked sets (in-memory fallback)
# ===========================================================================


class TestMyProgressInMemory:
    """Tests for GET /sets/my-progress when DB is disabled."""

    def test_returns_empty_progress(self):
        """In-memory fallback returns empty progress list."""
        resp = client.get("/sets/my-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress"] == []
        assert data["total"] == 0

    def test_response_schema(self):
        """Verify response has required keys."""
        resp = client.get("/sets/my-progress")
        data = resp.json()
        assert "progress" in data
        assert "total" in data
        assert isinstance(data["progress"], list)
        assert isinstance(data["total"], int)


# ===========================================================================
# GET /sets/my-progress — my tracked sets (mocked DB)
# ===========================================================================


class TestMyProgressMockedDB:
    """Tests for GET /sets/my-progress with mocked database."""

    def test_happy_path_returns_tracked_sets(self):
        """Returns list of tracked sets with completion percentages."""
        conn, ctx = _mock_conn_ctx()
        row1 = _make_my_progress_row(SET_ID, "Base Set", "pokemon", 102, 50, 49.02)
        row2 = _make_my_progress_row(SET_ID_2, "Alpha", "mtg", 295, 10, 3.39)
        conn.fetch = AsyncMock(return_value=[row1, row2])
        conn.fetchval = AsyncMock(return_value=2)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets/my-progress")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["progress"]) == 2
        p1 = data["progress"][0]
        assert p1["set_name"] == "Base Set"
        assert p1["owned_count"] == 50
        assert p1["completion_pct"] == 49.02

    def test_with_category_filter(self):
        """Filtering by category_id works."""
        conn, ctx = _mock_conn_ctx()
        row = _make_my_progress_row(SET_ID, "Base Set", "pokemon")
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchval = AsyncMock(return_value=1)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets/my-progress?category_id=pokemon")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_progress_entry_schema(self):
        """Each progress entry has the expected fields and types."""
        conn, ctx = _mock_conn_ctx()
        row = _make_my_progress_row()
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchval = AsyncMock(return_value=1)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets/my-progress")

        entry = resp.json()["progress"][0]
        assert isinstance(entry["set_id"], str)
        assert isinstance(entry["set_name"], str)
        assert isinstance(entry["category_id"], str)
        assert isinstance(entry["total_items"], int)
        assert isinstance(entry["owned_count"], int)
        assert isinstance(entry["completion_pct"], float)
        # Optional fields
        assert "image_url" in entry
        assert "notes" in entry
        assert "updated_at" in entry

    def test_empty_progress_db(self):
        """When user has no tracked sets, returns empty list."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        with patch("app.features.set_router.db_configured", return_value=True), \
             patch("app.features.set_router.get_conn", return_value=ctx):
            resp = client.get("/sets/my-progress")

        assert resp.status_code == 200
        assert resp.json()["progress"] == []
        assert resp.json()["total"] == 0
