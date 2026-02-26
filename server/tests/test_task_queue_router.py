"""Tests for app/features/task_queue_router.py — task queue endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The task queue router returns 503 when no DB pool is available.
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

VALID_UUID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# POST /tasks/enqueue — enqueue a background task
# ---------------------------------------------------------------------------

class TestEnqueueTask:
    def test_enqueue_no_db(self):
        """Enqueue returns 503 when DB pool is unavailable."""
        resp = client.post(
            "/tasks/enqueue",
            json={"task_type": "catalog_refresh", "payload": {}, "priority": 0},
        )
        assert resp.status_code == 503

    def test_enqueue_missing_task_type(self):
        """Rejects missing task_type field."""
        resp = client.post(
            "/tasks/enqueue",
            json={"payload": {}},
        )
        assert resp.status_code == 422

    def test_enqueue_priority_too_high(self):
        """Rejects priority above max (10)."""
        resp = client.post(
            "/tasks/enqueue",
            json={"task_type": "catalog_refresh", "payload": {}, "priority": 99},
        )
        assert resp.status_code == 422

    def test_enqueue_priority_negative(self):
        """Rejects negative priority."""
        resp = client.post(
            "/tasks/enqueue",
            json={"task_type": "catalog_refresh", "payload": {}, "priority": -1},
        )
        assert resp.status_code == 422

    def test_enqueue_no_body(self):
        """Rejects request with no body."""
        resp = client.post("/tasks/enqueue")
        assert resp.status_code == 422

    def test_enqueue_with_defaults(self):
        """Accepts request with only task_type (payload and priority have defaults)."""
        resp = client.post(
            "/tasks/enqueue",
            json={"task_type": "test_task"},
        )
        # Should be 503 (no DB), not 422 (validation error)
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}/status — get task status
# ---------------------------------------------------------------------------

class TestGetTaskStatus:
    def test_status_no_db(self):
        """Status returns 503 when DB pool is unavailable."""
        resp = client.get(f"/tasks/{VALID_UUID}/status")
        assert resp.status_code == 503

    def test_status_invalid_uuid(self):
        """Rejects invalid task_id format."""
        resp = client.get("/tasks/not-a-uuid/status")
        assert resp.status_code == 400

    def test_status_empty_uuid(self):
        """Rejects empty task_id path."""
        resp = client.get("/tasks//status")
        # FastAPI returns 404 for unmatched route or 307 redirect
        assert resp.status_code in (404, 307, 405)
