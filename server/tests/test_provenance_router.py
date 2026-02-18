"""
Tests for app/features/provenance_router.py — provenance timeline and event endpoints.

Covers:
  - GET /provenance/items/{item_id} — in-memory fallback (DB_ENABLED=false)
  - GET /provenance/items/{item_id} — mocked DB: happy path, ownership check, empty timeline
  - POST /provenance/items/{item_id}/events — in-memory fallback
  - POST /provenance/items/{item_id}/events — mocked DB: happy path, ownership check
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

ITEM_ID = str(uuid4())
OTHER_ITEM_ID = str(uuid4())


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


# ---------------------------------------------------------------------------
# GET /provenance/items/{item_id} — in-memory fallback (DB_ENABLED=false)
# ---------------------------------------------------------------------------


class TestGetProvenanceInMemory:
    """Tests for GET /provenance/items/{item_id} when DB is disabled."""

    def test_returns_new_timeline_for_unknown_item(self):
        """First request for an item creates a default 'added' event."""
        new_id = str(uuid4())
        resp = client.get(f"/provenance/items/{new_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == new_id
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "added"
        assert data["events"][0]["user_id"] == "dev-user-local"
        assert data["authenticity_signals"] == []

    def test_returns_existing_timeline_on_repeat_call(self):
        """Second call for the same item returns the previously created timeline."""
        stable_id = str(uuid4())
        resp1 = client.get(f"/provenance/items/{stable_id}")
        assert resp1.status_code == 200
        resp2 = client.get(f"/provenance/items/{stable_id}")
        assert resp2.status_code == 200
        assert resp2.json()["item_id"] == stable_id
        assert resp2.json()["created_at"] == resp1.json()["created_at"]

    def test_response_schema(self):
        """Verify all expected fields exist in the response."""
        resp = client.get(f"/provenance/items/{str(uuid4())}")
        data = resp.json()
        assert "item_id" in data
        assert "created_at" in data
        assert "events" in data
        assert "authenticity_signals" in data
        event = data["events"][0]
        assert "event_id" in event
        assert "item_id" in event
        assert "user_id" in event
        assert "event_type" in event
        assert "timestamp" in event

    def test_pagination_limits_events(self):
        """Pagination params limit the returned events in in-memory mode."""
        paged_id = str(uuid4())
        # First create the timeline
        client.get(f"/provenance/items/{paged_id}")
        # Add a second event via POST so there are 2 events
        client.post(
            f"/provenance/items/{paged_id}/events",
            json={
                "user_id": "dev-user-local",
                "event_type": "verified",
            },
        )
        # Request with limit=1
        resp = client.get(f"/provenance/items/{paged_id}?limit=1&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()["events"]) == 1


# ---------------------------------------------------------------------------
# GET /provenance/items/{item_id} — mocked DB (ownership check)
# ---------------------------------------------------------------------------


class TestGetProvenanceMockedDB:
    """Tests for GET /provenance/items/{item_id} with mocked database."""

    def test_happy_path_returns_timeline(self):
        """When the item belongs to the user and has events, return full timeline."""
        conn, ctx = _mock_conn_ctx()

        now = datetime.now(timezone.utc)
        # Ownership check succeeds
        conn.fetchval = AsyncMock(return_value=1)
        # Return two provenance events
        row1 = {
            "id": str(uuid4()),
            "item_id": ITEM_ID,
            "user_id": "dev-user-local",
            "event_type": "added",
            "note": "Initial add",
            "source": "manual",
            "metadata": "{}",
            "created_at": now,
        }
        row2 = {
            "id": str(uuid4()),
            "item_id": ITEM_ID,
            "user_id": "dev-user-local",
            "event_type": "verified",
            "note": None,
            "source": "receipt",
            "metadata": "{}",
            "created_at": now,
        }
        conn.fetch = AsyncMock(return_value=[row1, row2])

        with patch("app.features.provenance_router.db_configured", return_value=True), \
             patch("app.features.provenance_router.get_conn", return_value=ctx):
            resp = client.get(f"/provenance/items/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM_ID
        assert len(data["events"]) == 2
        assert data["events"][0]["event_type"] == "added"
        assert data["events"][1]["event_type"] == "verified"
        # Authenticity signals derived from events
        assert "owner_verified" in data["authenticity_signals"]
        assert "receipt_on_file" in data["authenticity_signals"]

    def test_item_not_owned_returns_404(self):
        """When ownership check fails (fetchval returns None), return 404."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=None)

        with patch("app.features.provenance_router.db_configured", return_value=True), \
             patch("app.features.provenance_router.get_conn", return_value=ctx):
            resp = client.get(f"/provenance/items/{ITEM_ID}")

        assert resp.status_code == 404

    def test_no_events_returns_empty_timeline(self):
        """When item exists but has no provenance events, return empty events list."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.provenance_router.db_configured", return_value=True), \
             patch("app.features.provenance_router.get_conn", return_value=ctx):
            resp = client.get(f"/provenance/items/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM_ID
        assert data["events"] == []
        assert data["authenticity_signals"] == []

    def test_graded_event_produces_authenticity_signal(self):
        """A 'graded' event type adds 'professionally_graded' to signals."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=1)
        row = {
            "id": str(uuid4()),
            "item_id": ITEM_ID,
            "user_id": "dev-user-local",
            "event_type": "graded",
            "note": "PSA 9",
            "source": "manual",
            "metadata": "{}",
            "created_at": datetime.now(timezone.utc),
        }
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.provenance_router.db_configured", return_value=True), \
             patch("app.features.provenance_router.get_conn", return_value=ctx):
            resp = client.get(f"/provenance/items/{ITEM_ID}")

        assert resp.status_code == 200
        assert "professionally_graded" in resp.json()["authenticity_signals"]


# ---------------------------------------------------------------------------
# POST /provenance/items/{item_id}/events — in-memory fallback
# ---------------------------------------------------------------------------


class TestAppendEventInMemory:
    """Tests for POST /provenance/items/{item_id}/events when DB is disabled."""

    def test_append_event_to_existing_timeline(self):
        """Appending an event to an existing timeline returns the updated timeline."""
        post_id = str(uuid4())
        # First create the timeline via GET
        client.get(f"/provenance/items/{post_id}")

        resp = client.post(
            f"/provenance/items/{post_id}/events",
            json={
                "user_id": "dev-user-local",
                "event_type": "graded",
                "note": "PSA 10",
                "source": "receipt",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 2
        assert data["events"][1]["event_type"] == "graded"
        assert data["events"][1]["note"] == "PSA 10"

    def test_append_event_not_found_returns_404(self):
        """Appending to a non-existent timeline (never created via GET) returns 404."""
        missing_id = str(uuid4())
        resp = client.post(
            f"/provenance/items/{missing_id}/events",
            json={
                "user_id": "dev-user-local",
                "event_type": "added",
            },
        )
        assert resp.status_code == 404

    def test_invalid_event_type_returns_422(self):
        """An invalid event_type fails Pydantic validation (422)."""
        ev_id = str(uuid4())
        client.get(f"/provenance/items/{ev_id}")
        resp = client.post(
            f"/provenance/items/{ev_id}/events",
            json={
                "user_id": "dev-user-local",
                "event_type": "INVALID",
            },
        )
        assert resp.status_code == 422

    def test_missing_user_id_returns_422(self):
        """Missing user_id in the body triggers 422."""
        ev_id = str(uuid4())
        client.get(f"/provenance/items/{ev_id}")
        resp = client.post(
            f"/provenance/items/{ev_id}/events",
            json={
                "event_type": "added",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /provenance/items/{item_id}/events — mocked DB (ownership check)
# ---------------------------------------------------------------------------


class TestAppendEventMockedDB:
    """Tests for POST /provenance/items/{item_id}/events with mocked database."""

    def test_append_event_success(self):
        """When the item belongs to the user, the event is inserted and timeline returned."""
        conn, ctx = _mock_conn_ctx()

        now = datetime.now(timezone.utc)
        # Ownership check succeeds
        conn.fetchval = AsyncMock(return_value=1)
        conn.execute = AsyncMock(return_value="INSERT 0 1")
        # The endpoint calls get_provenance internally to return the full timeline
        row = {
            "id": str(uuid4()),
            "item_id": ITEM_ID,
            "user_id": "dev-user-local",
            "event_type": "added",
            "note": None,
            "source": "manual",
            "metadata": "{}",
            "created_at": now,
        }
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.provenance_router.db_configured", return_value=True), \
             patch("app.features.provenance_router.get_conn", return_value=ctx):
            resp = client.post(
                f"/provenance/items/{ITEM_ID}/events",
                json={
                    "user_id": "dev-user-local",
                    "event_type": "purchase",
                    "note": "Bought from seller",
                    "source": "marketplace",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM_ID

    def test_append_event_not_owned_returns_404(self):
        """When ownership check fails, return 404 (not 403)."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=None)

        with patch("app.features.provenance_router.db_configured", return_value=True), \
             patch("app.features.provenance_router.get_conn", return_value=ctx):
            resp = client.post(
                f"/provenance/items/{ITEM_ID}/events",
                json={
                    "user_id": "dev-user-local",
                    "event_type": "added",
                },
            )

        assert resp.status_code == 404
