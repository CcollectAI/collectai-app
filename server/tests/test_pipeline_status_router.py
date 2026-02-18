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


def test_pipeline_status_db_error():
    """When a DB query fails, returns status=error with message."""
    conn, ctx = _mock_conn_ctx()
    conn.fetch = AsyncMock(side_effect=RuntimeError("connection lost"))

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"
    assert "connection lost" in data["message"]
    assert data["training"] == []
    assert data["ingest"] == {}


def test_pipeline_status_stale_detection():
    """Models trained > 48h ago should be flagged as stale."""
    from datetime import timedelta

    conn, ctx = _mock_conn_ctx()
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=72)  # 3 days old

    conn.fetch = AsyncMock(side_effect=[
        # training_rows — one fresh, one stale
        [
            {"category": "pokemon", "version": "v2.1", "is_active": True,
             "train_size": 500, "mae": 5.2, "created_at": now},
            {"category": "funko", "version": "v1.0", "is_active": True,
             "train_size": 100, "mae": 12.0, "created_at": old},
        ],
        # ingest_rows
        [
            {"category": "pokemon", "item_count": 150, "last_updated": now},
            {"category": "funko", "item_count": 30, "last_updated": old},
        ],
    ])
    conn.fetchval = AsyncMock(side_effect=[500, now])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "stale"
    assert "funko" in data["stale_categories"]
    assert "pokemon" not in data["stale_categories"]
    assert data["training"]["models_count"] == 2
    assert data["ingest"]["categories_count"] == 2


def test_pipeline_status_empty_market_hits():
    """When no market_hits exist, total_hits=0 and latest_hit_at=None."""
    conn, ctx = _mock_conn_ctx()
    now = datetime.now(timezone.utc)

    conn.fetch = AsyncMock(side_effect=[
        [{"category": "pokemon", "version": "v2.1", "is_active": True,
          "train_size": 500, "mae": 5.2, "created_at": now}],
        [{"category": "pokemon", "item_count": 150, "last_updated": now}],
    ])
    conn.fetchval = AsyncMock(side_effect=[0, None])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    data = r.json()
    assert data["market_data"]["total_hits"] == 0
    assert data["market_data"]["latest_hit_at"] is None


def test_pipeline_status_no_models_no_ingest():
    """Empty model_registry and category_items returns healthy with 0 counts."""
    conn, ctx = _mock_conn_ctx()

    conn.fetch = AsyncMock(side_effect=[[], []])
    conn.fetchval = AsyncMock(side_effect=[0, None])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["training"]["models_count"] == 0
    assert data["ingest"]["categories_count"] == 0
    assert data["stale_categories"] == []


def test_pipeline_status_none_mae():
    """Model with mae=None should not crash."""
    conn, ctx = _mock_conn_ctx()
    now = datetime.now(timezone.utc)

    conn.fetch = AsyncMock(side_effect=[
        [{"category": "test", "version": "v1", "is_active": True,
          "train_size": 10, "mae": None, "created_at": now}],
        [],
    ])
    conn.fetchval = AsyncMock(side_effect=[0, None])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    model = r.json()["training"]["models"][0]
    assert model["mae"] is None
