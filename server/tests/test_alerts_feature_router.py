"""Tests for app/features/alerts_feature_router.py — price alert endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The alerts router uses in-memory store when DB is disabled, so CRUD works offline.
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


# ---------------------------------------------------------------------------
# GET /alerts/mine — list alerts
# ---------------------------------------------------------------------------

class TestListAlerts:
    def test_list_alerts_returns_200(self):
        """List alerts returns 200 with empty list in offline mode."""
        resp = client.get("/alerts/mine")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    def test_list_alerts_with_pagination(self):
        """Accepts pagination query params."""
        resp = client.get("/alerts/mine", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /alerts/mine — create alert
# ---------------------------------------------------------------------------

class TestCreateAlert:
    def test_create_alert_returns_200(self):
        """Create alert returns 200 in offline mode (in-memory store)."""
        resp = client.post(
            "/alerts/mine",
            json={
                "trigger_type": "below_threshold",
                "threshold_value": 50.0,
                "item_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trigger_type"] == "below_threshold"
        assert data["threshold_value"] == 50.0
        assert data["active"] is True

    def test_create_alert_category_trend(self):
        """Create category trend alert."""
        resp = client.post(
            "/alerts/mine",
            json={
                "trigger_type": "category_trend",
                "category": "pokemon_tcg",
                "direction": "up",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trigger_type"] == "category_trend"
        assert data["category"] == "pokemon_tcg"

    def test_create_alert_invalid_trigger_type(self):
        """Rejects invalid trigger_type."""
        resp = client.post(
            "/alerts/mine",
            json={
                "trigger_type": "invalid_type",
                "threshold_value": 50.0,
            },
        )
        assert resp.status_code == 422

    def test_create_alert_negative_threshold(self):
        """Rejects negative threshold_value."""
        resp = client.post(
            "/alerts/mine",
            json={
                "trigger_type": "below_threshold",
                "threshold_value": -10.0,
            },
        )
        assert resp.status_code == 422

    def test_create_alert_threshold_too_high(self):
        """Rejects threshold_value exceeding 1,000,000."""
        resp = client.post(
            "/alerts/mine",
            json={
                "trigger_type": "below_threshold",
                "threshold_value": 2_000_000,
            },
        )
        assert resp.status_code == 422

    def test_create_alert_no_body(self):
        """Rejects request with no body."""
        resp = client.post("/alerts/mine")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /alerts/mine/{alert_id} — delete alert
# ---------------------------------------------------------------------------

class TestDeleteAlert:
    def test_delete_nonexistent_alert(self):
        """Deleting a non-existent alert returns 404 in offline mode."""
        resp = client.delete("/alerts/mine/00000000-0000-0000-0000-000000000099")
        assert resp.status_code == 404

    def test_create_then_delete_alert(self):
        """Create an alert then delete it successfully."""
        # Create
        create_resp = client.post(
            "/alerts/mine",
            json={
                "trigger_type": "below_threshold",
                "threshold_value": 25.0,
            },
        )
        assert create_resp.status_code == 200
        alert_id = create_resp.json()["id"]

        # Delete
        delete_resp = client.delete(f"/alerts/mine/{alert_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# GET /alerts/trigger-history — trigger history
# ---------------------------------------------------------------------------

class TestTriggerHistory:
    def test_trigger_history_offline(self):
        """Returns empty triggers in offline mode."""
        resp = client.get("/alerts/trigger-history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["triggers"] == []
        assert data["unread_count"] == 0


# ---------------------------------------------------------------------------
# POST /alerts/trigger-history/{trigger_id}/read — mark trigger read
# ---------------------------------------------------------------------------

class TestMarkTriggerRead:
    def test_mark_trigger_read_offline(self):
        """Mark trigger read returns 200 in offline mode."""
        resp = client.post("/alerts/trigger-history/00000000-0000-0000-0000-000000000099/read")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
