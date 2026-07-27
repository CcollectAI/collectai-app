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

    # ONE fetch, not two.
    #
    # The route no longer queries model_registry — it hardcodes
    # `training_rows: list = []` because that table has documented schema
    # drift (stale Sept-2025 rows, missing category / is_active /
    # train_size / mae) and the real source of truth for models is the
    # `disk:active` symlinks under /opt/collectors/artifacts. See the
    # comment at pipeline_status_router.py:43.
    #
    # This mock still supplied a model_registry result first, so the single
    # remaining fetch returned the TRAINING rows and the route raised
    # KeyError: 'last_updated' on them. That read like a broken endpoint;
    # it is not — GET /pipeline/status returns 200 with all 54 categories
    # in production, verified 2026-07-27.
    conn.fetch = AsyncMock(side_effect=[
        # ingest_rows (category_items) — the only fetch the route makes
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
    assert data["status"] == "unknown"
    # models_count is 0 by construction while model_registry is bypassed.
    # Pinned rather than dropped: if someone re-enables that query, this
    # says out loud that the endpoint's model history is currently empty
    # ON PURPOSE and is not evidence of a training failure.
    assert data["training"]["models_count"] == 0
    assert data["training"]["models"] == []
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

    # Only the ingest fetch — model_registry is bypassed (see the note in
    # test_pipeline_status_healthy).
    conn.fetch = AsyncMock(side_effect=[
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
    # Staleness is derived from model_registry, which the route bypasses, so
    # it cannot currently fire. The endpoint now says "unknown" instead of
    # claiming "healthy" with nothing to assess — asserting "healthy" here
    # would be pinning the bug this test exists to catch.
    assert data["status"] == "unknown"
    assert data["stale_categories"] == []
    assert data["training"]["models_count"] == 0
    assert data["ingest"]["categories_count"] == 2


def test_pipeline_status_empty_market_hits():
    """When no market_hits exist, total_hits=0 and latest_hit_at=None."""
    conn, ctx = _mock_conn_ctx()
    now = datetime.now(timezone.utc)

    conn.fetch = AsyncMock(side_effect=[
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

    conn.fetch = AsyncMock(side_effect=[[]])
    conn.fetchval = AsyncMock(side_effect=[0, None])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    data = r.json()
    # "unknown", not "healthy": with no model history there is nothing to
    # assess, and answering "healthy" is the failure this endpoint is meant
    # to detect.
    assert data["status"] == "unknown"
    assert data["training"]["models_count"] == 0
    assert data["ingest"]["categories_count"] == 0
    assert data["stale_categories"] == []


def test_pipeline_status_model_registry_is_bypassed():
    """No model rows are returned at all while model_registry is bypassed.

    This was `test_pipeline_status_none_mae`, asserting that a model row with
    mae=None did not crash the formatter. That row can no longer exist: the
    route hardcodes `training_rows = []`, so `models` is always empty and
    indexing `models[0]` raised. Repointed to assert the actual contract
    rather than deleted, so that re-enabling the query surfaces here.
    """
    conn, ctx = _mock_conn_ctx()

    conn.fetch = AsyncMock(side_effect=[[]])
    conn.fetchval = AsyncMock(side_effect=[0, None])

    with patch("app.routes.pipeline_status_router.db_configured", return_value=True), \
         patch("app.routes.pipeline_status_router.get_conn", return_value=ctx):
        r = client.get("/pipeline/status")

    assert r.status_code == 200
    training = r.json()["training"]
    assert training["models"] == []
    assert training["models_count"] == 0
