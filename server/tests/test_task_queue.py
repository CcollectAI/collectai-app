"""Tests for background task queue.

Tests cover:
- Task handler registration via decorator
- Built-in handler presence and execution
- Router endpoints (enqueue + status) in offline mode
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from app.lib.task_worker import _handlers, register_task  # noqa: E402


# ---------------------------------------------------------------------------
# Handler registration tests
# ---------------------------------------------------------------------------


class TestRegisterTask:
    def test_register_task(self):
        """Test task handler registration via decorator."""
        @register_task("test_type")
        async def handler(payload):
            return {"done": True}

        assert "test_type" in _handlers
        assert _handlers["test_type"] is handler
        # Cleanup
        del _handlers["test_type"]

    def test_register_overwrites(self):
        """Registering the same task_type replaces the previous handler."""
        @register_task("overwrite_test")
        async def handler_a(payload):
            return {"v": "a"}

        @register_task("overwrite_test")
        async def handler_b(payload):
            return {"v": "b"}

        assert _handlers["overwrite_test"] is handler_b
        # Cleanup
        del _handlers["overwrite_test"]


# ---------------------------------------------------------------------------
# Built-in handler tests
# ---------------------------------------------------------------------------


class TestBuiltinHandlers:
    def test_builtin_handlers_registered(self):
        """Verify built-in task handlers are registered."""
        assert "catalog_refresh" in _handlers
        assert "image_optimize" in _handlers
        assert "market_persist" in _handlers
        assert "provenance_log" in _handlers

    @pytest.mark.asyncio
    async def test_catalog_refresh_handler(self):
        handler = _handlers["catalog_refresh"]
        result = await handler({"category_id": "pokemon_tcg"})
        assert result["category_id"] == "pokemon_tcg"
        assert result["status"] == "refreshed"

    @pytest.mark.asyncio
    async def test_image_optimize_handler(self):
        handler = _handlers["image_optimize"]
        result = await handler({"image_url": "https://example.com/img.jpg"})
        assert result["optimized"] is True
        assert result["image_url"] == "https://example.com/img.jpg"

    @pytest.mark.asyncio
    async def test_market_persist_handler(self):
        handler = _handlers["market_persist"]
        result = await handler({"item_id": "abc-123"})
        assert result["persisted"] is True
        assert result["item_id"] == "abc-123"

    @pytest.mark.asyncio
    async def test_provenance_log_handler(self):
        handler = _handlers["provenance_log"]
        result = await handler({"item_id": "abc-123", "event": "price_change"})
        assert result["logged"] is True
        assert result["item_id"] == "abc-123"
        assert result["event"] == "price_change"

    @pytest.mark.asyncio
    async def test_catalog_refresh_empty_payload(self):
        """Handler works with missing keys in payload."""
        handler = _handlers["catalog_refresh"]
        result = await handler({})
        assert result["category_id"] is None
        assert result["status"] == "refreshed"


# ---------------------------------------------------------------------------
# Router endpoint tests (offline mode — no DB pool)
# ---------------------------------------------------------------------------


class TestTaskQueueRouter:
    @pytest.fixture(autouse=True)
    def _client(self):
        from starlette.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    def test_enqueue_no_db(self):
        """Enqueue returns 503 when DB pool is unavailable."""
        resp = self.client.post(
            "/tasks/enqueue",
            json={"task_type": "catalog_refresh", "payload": {}, "priority": 0},
        )
        assert resp.status_code == 503

    def test_enqueue_validation_priority(self):
        """Enqueue rejects priority out of range."""
        resp = self.client.post(
            "/tasks/enqueue",
            json={"task_type": "catalog_refresh", "payload": {}, "priority": 99},
        )
        assert resp.status_code == 422

    def test_enqueue_validation_missing_type(self):
        """Enqueue rejects missing task_type."""
        resp = self.client.post(
            "/tasks/enqueue",
            json={"payload": {}},
        )
        assert resp.status_code == 422

    def test_status_no_db(self):
        """Status returns 503 when DB pool is unavailable."""
        resp = self.client.get("/tasks/00000000-0000-0000-0000-000000000001/status")
        assert resp.status_code == 503

    def test_v1_enqueue_no_db(self):
        """V1 alias also works."""
        resp = self.client.post(
            "/v1/tasks/enqueue",
            json={"task_type": "test", "payload": {}},
        )
        assert resp.status_code == 503
