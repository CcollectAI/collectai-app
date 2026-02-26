"""Tests for app/features/activity_router.py — activity feed endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The activity_router endpoints require a DB pool, so these tests verify:
- Input validation (UUID format)
- Auth dependency (dev mode bypass)
- Offline mode responses when pool is None (503)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

DEV_USER_ID = os.environ.get("DEV_USER_ID", "dev-user-local")
VALID_UUID = "00000000-0000-0000-0000-000000000099"


# ---------------------------------------------------------------------------
# GET /activity/{user_id} — get user activity feed
# ---------------------------------------------------------------------------

class TestGetUserActivity:
    def test_get_activity_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.get(f"/activity/{VALID_UUID}")
        assert resp.status_code == 503

    def test_get_activity_invalid_uuid(self):
        """Rejects invalid UUID format."""
        resp = client.get("/activity/not-a-uuid")
        assert resp.status_code == 400

    def test_get_activity_with_pagination(self):
        """Accepts limit and offset query params (still 503 because no DB)."""
        resp = client.get(f"/activity/{VALID_UUID}", params={"limit": 10, "offset": 5})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# POST /activity/log — log a new activity
# ---------------------------------------------------------------------------

class TestLogActivity:
    def test_log_activity_no_db(self):
        """Returns 503 when DB pool is unavailable."""
        resp = client.post(
            "/activity/log",
            json={
                "activity_type": "item_added",
                "title": "Added a new Pokemon card",
                "description": "Charizard VMAX",
                "is_public": True,
            },
        )
        assert resp.status_code == 503

    def test_log_activity_missing_required_fields(self):
        """Rejects request missing required fields."""
        resp = client.post("/activity/log", json={})
        assert resp.status_code == 422

    def test_log_activity_missing_title(self):
        """Rejects request missing title."""
        resp = client.post(
            "/activity/log",
            json={"activity_type": "item_added"},
        )
        assert resp.status_code == 422

    def test_log_activity_missing_activity_type(self):
        """Rejects request missing activity_type."""
        resp = client.post(
            "/activity/log",
            json={"title": "Something happened"},
        )
        assert resp.status_code == 422

    def test_log_activity_no_body(self):
        """Rejects request with no body at all."""
        resp = client.post("/activity/log")
        assert resp.status_code == 422
