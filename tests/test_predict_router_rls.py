"""
Tests for app/features/predict_router.py — RLS (ownership) fixes.

Separate from the existing test_predict_router.py and test_predict_evidence.py.
These tests specifically verify the combined ownership check that was added
as part of the RLS fix:
  - GET /predict/evidence/{item_id} — ownership verified via single query
  - GET /predict/evidence/{item_id} — non-owned item returns 404 (not 403!)
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
# GET /predict/evidence/{item_id} — ownership check (RLS)
# ---------------------------------------------------------------------------


class TestPriceEvidenceOwnership:
    """Verify the ownership check uses a single query and returns 404 for non-owned items."""

    def test_owned_item_with_prediction(self):
        """When item belongs to user and has a prediction, return full evidence."""
        conn, ctx = _mock_conn_ctx()

        now = datetime(2026, 2, 10, 15, 0, 0, tzinfo=timezone.utc)

        # fetchval (ownership check) => returns 1 (item exists for this user)
        conn.fetchval = AsyncMock(return_value=1)
        # fetchrow (prediction query) => returns prediction data
        conn.fetchrow = AsyncMock(return_value={
            "q10": 45.0,
            "q50": 85.0,
            "q90": 160.0,
            "conf_score": 0.72,
            "explanation": "Based on 8 comparable eBay sales",
            "evidence_summary": '{"sources": [{"source": "ebay", "count": 8, "avg_price": 82.50}], "total_comps": 8}',
            "evidence_hit_ids": '["id-1", "id-2"]',
            "asof": now,
        })

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["q10"] == 45.0
        assert data["q50"] == 85.0
        assert data["q90"] == 160.0
        assert data["confidence_score"] == 0.72
        assert data["explanation"] == "Based on 8 comparable eBay sales"
        assert len(data["evidence_hit_ids"]) == 2
        assert data["evidence_summary"]["total_comps"] == 8
        assert data["prediction_at"] == "2026-02-10T15:00:00+00:00"

        # Verify the ownership query checked both item id AND user_id
        ownership_call = conn.fetchval.call_args
        ownership_query = ownership_call[0][0]
        assert "user_id" in ownership_query
        assert "items" in ownership_query

    def test_non_owned_item_returns_404_not_403(self):
        """When item does not belong to user, return 404 (not 403, to prevent info leak)."""
        conn, ctx = _mock_conn_ctx()
        # Ownership check returns None => item not found for this user
        conn.fetchval = AsyncMock(return_value=None)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_owned_item_no_prediction(self):
        """When item belongs to user but has no prediction, return empty evidence."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None
        assert data["q50"] is None
        assert data["evidence_summary"] is None
        assert data["evidence_hit_ids"] == []

    def test_db_disabled_returns_empty(self):
        """When DB is disabled, return empty evidence without ownership check."""
        # DB_ENABLED=false is the default in tests, no need to patch
        resp = client.get(f"/predict/evidence/{ITEM_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None
        assert data["q50"] is None

    def test_runtime_error_returns_empty_not_500(self):
        """When DB pool is unavailable (RuntimeError), return empty response, not 500."""
        conn, ctx = _mock_conn_ctx()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("Pool not initialized"))

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None

    def test_ownership_check_uses_single_query(self):
        """The ownership check should use a single SELECT...WHERE id=$1 AND user_id=$2 query."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 200

        # fetchval should be called exactly once (the ownership check)
        assert conn.fetchval.call_count == 1
        query = conn.fetchval.call_args[0][0]
        # Both $1 (item_id) and $2 (user_id) should be in one query
        assert "$1" in query
        assert "$2" in query
        assert "user_id" in query

    def test_fallback_explanation_when_none_stored(self):
        """When no explanation is stored, the endpoint tries to generate one."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=1)

        now = datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc)
        # Prediction row with no explanation
        conn.fetchrow = AsyncMock(side_effect=[
            {
                "q10": 10.0,
                "q50": 20.0,
                "q90": 30.0,
                "conf_score": 0.5,
                "explanation": None,
                "evidence_summary": None,
                "evidence_hit_ids": None,
                "asof": now,
            },
            # Second fetchrow call for item details (fallback explanation)
            {
                "title": "Charizard Base Set",
                "category": "pokemon",
                "attributes_json": "{}",
            },
        ])

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx), \
             patch(
                 "app.ml.explainer.generate_simple_explanation",
                 return_value="Price based on pokemon market trends",
             ):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["q50"] == 20.0
        assert data["explanation"] == "Price based on pokemon market trends"

    def test_evidence_summary_parsed_from_json_string(self):
        """The evidence_summary field is correctly parsed from a JSON string."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchval = AsyncMock(return_value=1)

        now = datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc)
        summary_json = (
            '{"sources": ['
            '{"source": "ebay", "count": 10, "avg_price": 100.0},'
            '{"source": "tcgplayer", "count": 5, "avg_price": 90.0}'
            '], "total_comps": 15}'
        )
        conn.fetchrow = AsyncMock(return_value={
            "q10": 70.0,
            "q50": 100.0,
            "q90": 140.0,
            "conf_score": 0.9,
            "explanation": "High confidence",
            "evidence_summary": summary_json,
            "evidence_hit_ids": '["h1", "h2", "h3"]',
            "asof": now,
        })

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", return_value=ctx):
            resp = client.get(f"/predict/evidence/{ITEM_ID}")

        assert resp.status_code == 200
        data = resp.json()
        summary = data["evidence_summary"]
        assert summary["total_comps"] == 15
        assert len(summary["sources"]) == 2
        assert summary["sources"][0]["source"] == "ebay"
        assert summary["sources"][1]["source"] == "tcgplayer"
        assert len(data["evidence_hit_ids"]) == 3
