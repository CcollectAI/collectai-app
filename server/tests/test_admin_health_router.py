"""Tests for app/features/admin_health_router.py — Worker health endpoint.

Covers:
  - GET /admin/worker-health returns 403 without OPS_API_KEY set
  - GET /admin/worker-health returns 403 with wrong key
  - GET /admin/worker-health returns 200 with correct key

All tests mock get_worker_health() so no real worker state is needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

MOCK_HEALTH = [
    {
        "name": "price_monitor",
        "last_run_at": "2026-03-15T12:00:00Z",
        "last_status": "ok",
        "run_count": 42,
        "average_duration_s": 3.5,
        "status": "ok",
        "minutes_overdue": 0,
    }
]


class TestWorkerHealthNoKey:
    """OPS_API_KEY not set at all — should return 403."""

    @patch.dict(os.environ, {"OPS_API_KEY": ""}, clear=False)
    def test_returns_403_without_ops_key(self):
        resp = client.get("/admin/worker-health")
        assert resp.status_code == 403
        assert "not configured" in resp.json()["detail"]


class TestWorkerHealthWrongKey:
    """OPS_API_KEY is set but caller sends wrong value — should return 403."""

    @patch.dict(os.environ, {"OPS_API_KEY": "correct-secret"}, clear=False)
    def test_returns_403_with_wrong_key(self):
        resp = client.get(
            "/admin/worker-health",
            headers={"X-Ops-Key": "wrong-secret"},
        )
        assert resp.status_code == 403
        assert "Invalid" in resp.json()["detail"]

    @patch.dict(os.environ, {"OPS_API_KEY": "correct-secret"}, clear=False)
    def test_returns_403_with_missing_header(self):
        resp = client.get("/admin/worker-health")
        assert resp.status_code == 403
        assert "Invalid" in resp.json()["detail"]


class TestWorkerHealthSuccess:
    """OPS_API_KEY is set and caller provides correct key — should return 200."""

    @patch.dict(os.environ, {"OPS_API_KEY": "test-ops-key"}, clear=False)
    @patch("app.features.admin_health_router.get_worker_health", return_value=MOCK_HEALTH)
    def test_returns_200_with_correct_key(self, mock_health):
        resp = client.get(
            "/admin/worker-health",
            headers={"X-Ops-Key": "test-ops-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "price_monitor"
        assert data[0]["status"] == "ok"
        mock_health.assert_called_once()
