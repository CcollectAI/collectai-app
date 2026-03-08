"""
Tests for notification history endpoints in app/features/notification_router.py.

Covers:
  - GET  /notifications/history           — paginated history (DB-off fallback)
  - PATCH /notifications/{id}/read        — mark single as read (DB-off = 503)
  - POST /notifications/mark-all-read     — mark all read (DB-off fallback)
  - Query param validation (limit, offset, unread_only)
  - UUID validation on notification_id
  - Router mount verification

With DB_ENABLED=false and DEV_MODE=true, endpoints take their no-DB code paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

VALID_UUID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# GET /notifications/history — paginated notification history
# ---------------------------------------------------------------------------


class TestGetNotificationHistory:
    """Tests for GET /notifications/history."""

    def test_history_returns_empty_no_db(self):
        """With DB disabled, returns empty list with counts."""
        resp = client.get("/notifications/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["notifications"] == []
        assert data["total_count"] == 0
        assert data["unread_count"] == 0

    def test_history_response_shape(self):
        """Response must include notifications, total_count, and unread_count."""
        resp = client.get("/notifications/history")
        data = resp.json()
        assert "notifications" in data
        assert "total_count" in data
        assert "unread_count" in data
        assert isinstance(data["notifications"], list)
        assert isinstance(data["total_count"], int)
        assert isinstance(data["unread_count"], int)

    def test_history_default_pagination(self):
        """Default limit=20, offset=0 should work."""
        resp = client.get("/notifications/history")
        assert resp.status_code == 200

    def test_history_custom_pagination(self):
        """Custom limit and offset should be accepted."""
        resp = client.get("/notifications/history", params={"limit": 10, "offset": 5})
        assert resp.status_code == 200

    def test_history_limit_max_50(self):
        """limit > 50 should be rejected."""
        resp = client.get("/notifications/history", params={"limit": 100})
        assert resp.status_code == 422

    def test_history_limit_min_1(self):
        """limit < 1 should be rejected."""
        resp = client.get("/notifications/history", params={"limit": 0})
        assert resp.status_code == 422

    def test_history_negative_offset(self):
        """Negative offset should be rejected."""
        resp = client.get("/notifications/history", params={"offset": -1})
        assert resp.status_code == 422

    def test_history_unread_only_filter(self):
        """unread_only=true should be accepted."""
        resp = client.get("/notifications/history", params={"unread_only": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["notifications"] == []

    def test_history_unread_only_false(self):
        """unread_only=false (default) should be accepted."""
        resp = client.get("/notifications/history", params={"unread_only": False})
        assert resp.status_code == 200

    def test_history_v1_alias(self):
        """History endpoint should be available under /v1 prefix."""
        resp = client.get("/v1/notifications/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "notifications" in data


# ---------------------------------------------------------------------------
# PATCH /notifications/{notification_id}/read — mark single as read
# ---------------------------------------------------------------------------


class TestMarkNotificationRead:
    """Tests for PATCH /notifications/{notification_id}/read."""

    def test_mark_read_no_db(self):
        """Returns 503 when DB is not available."""
        resp = client.patch(f"/notifications/{VALID_UUID}/read")
        assert resp.status_code == 503

    def test_mark_read_invalid_uuid(self):
        """Rejects non-UUID notification_id."""
        resp = client.patch("/notifications/not-a-valid-uuid/read")
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("code") == "VALIDATION_ERROR"

    def test_mark_read_response_503_shape(self):
        """503 response should have standard error shape."""
        resp = client.patch(f"/notifications/{VALID_UUID}/read")
        assert resp.status_code == 503
        data = resp.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read — mark all as read
# ---------------------------------------------------------------------------


class TestMarkAllNotificationsRead:
    """Tests for POST /notifications/mark-all-read."""

    def test_mark_all_read_no_db(self):
        """With DB disabled, returns updated_count=0."""
        resp = client.post("/notifications/mark-all-read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_count"] == 0

    def test_mark_all_read_response_shape(self):
        """Response must include updated_count."""
        resp = client.post("/notifications/mark-all-read")
        data = resp.json()
        assert "updated_count" in data
        assert isinstance(data["updated_count"], int)

    def test_mark_all_read_v1_alias(self):
        """Mark-all-read should be available under /v1 prefix."""
        resp = client.post("/v1/notifications/mark-all-read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_count"] == 0


# ---------------------------------------------------------------------------
# Router mount verification
# ---------------------------------------------------------------------------


class TestNotificationHistoryRouterMount:
    """Verify the notification history endpoints are properly mounted."""

    def test_history_endpoint_exists(self):
        """GET /notifications/history should not 404."""
        resp = client.get("/notifications/history")
        assert resp.status_code != 404

    def test_mark_read_endpoint_exists(self):
        """PATCH /notifications/{id}/read should not 404."""
        resp = client.patch(f"/notifications/{VALID_UUID}/read")
        assert resp.status_code != 404

    def test_mark_all_read_endpoint_exists(self):
        """POST /notifications/mark-all-read should not 404."""
        resp = client.post("/notifications/mark-all-read")
        assert resp.status_code != 404

    def test_wrong_method_history(self):
        """POST to /notifications/history should be 405."""
        resp = client.post("/notifications/history")
        assert resp.status_code == 405

    def test_wrong_method_mark_all(self):
        """GET to /notifications/mark-all-read should be 405."""
        resp = client.get("/notifications/mark-all-read")
        assert resp.status_code == 405
