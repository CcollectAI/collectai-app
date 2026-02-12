"""Tests for app.routes.pipeline_status_router — GET /pipeline/status endpoint."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def _mock_conn_ctx():
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, ctx


def test_pipeline_status_db_disabled():
    """When DB is not configured, returns unknown status."""
    r = client.get("/pipeline/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "unknown"


def test_pipeline_status_with_db():
    """When DB is configured, returns training + ingest data."""
    conn, ctx = _mock_conn_ctx()
    now = datetime.now(timezone.utc)

    conn.fetch = AsyncMock(side_effect=[
        # training_rows (model_registry)
        [
            {
                "category": "pokemon",
                "version": "v2.1",
                "is_active": True,
                "train_size": 500,
                "mae": 5.2,
                "created_at": now,
            },
        ],
        # ingest_rows (category_items)
        [
            {
                "category": "pokemon",
                "item_count": 150,
                "last_updated": now,
            },
        ],
    ])
    conn.fetchval = AsyncMock(side_effect=[
        1000,  # market_hits count
        now,   # latest market_hit
    ])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["training"]["models_count"] == 1
    assert data["training"]["models"][0]["category"] == "pokemon"
    assert data["ingest"]["categories_count"] == 1
    assert data["market_data"]["total_hits"] == 1000


def test_pipeline_status_no_auth_required():
    """Pipeline status should be publicly accessible."""
    r = client.get("/pipeline/status")
    assert r.status_code == 200
