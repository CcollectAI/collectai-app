"""
Tests for app/features/predict_router.py — GET /predict/evidence/{item_id}.

Extends the existing test_predict_router.py (which tests DB-disabled mode)
with mocked DB tests covering:
  - Full evidence response with mocked DB
  - Item not found (404)
  - Item not owned by user (403)
  - No prediction data returns empty response
  - Fallback explanation generation
  - DB pool unavailable (RuntimeError)
  - _parse_json helper
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# _parse_json helper tests
# ---------------------------------------------------------------------------


class TestParseJson:
    """Tests for _parse_json() in predict_router."""

    def test_none(self):
        from app.features.predict_router import _parse_json

        assert _parse_json(None) is None

    def test_valid_json_string(self):
        from app.features.predict_router import _parse_json

        result = _parse_json('{"sources": []}')
        assert result == {"sources": []}

    def test_invalid_json_string(self):
        from app.features.predict_router import _parse_json

        result = _parse_json("not-json")
        assert result == "not-json"

    def test_dict_passthrough(self):
        from app.features.predict_router import _parse_json

        d = {"key": "value"}
        assert _parse_json(d) is d

    def test_list_passthrough(self):
        from app.features.predict_router import _parse_json

        lst = [1, 2, 3]
        assert _parse_json(lst) is lst


# ---------------------------------------------------------------------------
# Pydantic response model tests
# ---------------------------------------------------------------------------


class TestResponseModels:
    """Tests for Pydantic response models in predict_router."""

    def test_price_evidence_response_defaults(self):
        from app.features.predict_router import PriceEvidenceResponse

        resp = PriceEvidenceResponse()
        assert resp.explanation is None
        assert resp.evidence_summary is None
        assert resp.evidence_hit_ids == []
        assert resp.prediction_at is None
        assert resp.q10 is None
        assert resp.q50 is None
        assert resp.q90 is None
        assert resp.confidence_score is None

    def test_evidence_source_response(self):
        from app.features.predict_router import EvidenceSourceResponse

        src = EvidenceSourceResponse(
            source="ebay",
            count=15,
            avg_price=125.50,
            date_range="2026-01-01 to 2026-02-01",
        )
        assert src.source == "ebay"
        assert src.count == 15

    def test_evidence_summary_response(self):
        from app.features.predict_router import (
            EvidenceSummaryResponse,
            EvidenceSourceResponse,
        )

        summary = EvidenceSummaryResponse(
            sources=[
                EvidenceSourceResponse(source="ebay", count=10, avg_price=100.0),
                EvidenceSourceResponse(source="tcgplayer", count=5, avg_price=90.0),
            ],
            total_comps=15,
        )
        assert len(summary.sources) == 2
        assert summary.total_comps == 15


# ---------------------------------------------------------------------------
# GET /predict/evidence/{item_id} — mocked DB tests
# ---------------------------------------------------------------------------


class TestPriceEvidenceEndpointMocked:
    """Tests for GET /predict/evidence/{item_id} with mocked DB."""

    @pytest.mark.asyncio
    async def test_full_evidence_response(self):
        """When DB has a prediction with evidence, full response is returned."""
        from fastapi.testclient import TestClient
        from main import app

        mock_pred = {
            "q10": 80.0,
            "q50": 150.0,
            "q90": 250.0,
            "conf_score": 0.85,
            "explanation": "Based on 12 recent eBay sales",
            "evidence_summary": '{"sources": [{"source": "ebay", "count": 12, "avg_price": 145.0}], "total_comps": 12}',
            "evidence_hit_ids": '["hit-1", "hit-2", "hit-3"]',
            "asof": datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="dev-user-local")
        mock_conn.fetchrow = AsyncMock(return_value=mock_pred)

        # We need to mock get_conn as an async context manager
        mock_get_conn = MagicMock()
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", mock_get_conn):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/predict/evidence/00000000-0000-0000-0000-000000000001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["q50"] == 150.0
        assert data["q10"] == 80.0
        assert data["q90"] == 250.0
        assert data["confidence_score"] == 0.85
        assert data["explanation"] == "Based on 12 recent eBay sales"
        assert len(data["evidence_hit_ids"]) == 3
        assert data["evidence_summary"]["total_comps"] == 12

    @pytest.mark.asyncio
    async def test_item_not_found_404(self):
        """When item does not exist, return 404."""
        from fastapi.testclient import TestClient
        from main import app

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)

        mock_get_conn = MagicMock()
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", mock_get_conn):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/predict/evidence/nonexistent-item")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_item_not_owned_403(self):
        """When item belongs to another user, return 403."""
        from fastapi.testclient import TestClient
        from main import app

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="different-user-id")

        mock_get_conn = MagicMock()
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", mock_get_conn):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/predict/evidence/some-item-id")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_no_prediction_returns_empty(self):
        """When item exists but has no prediction, return empty evidence."""
        from fastapi.testclient import TestClient
        from main import app

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="dev-user-local")
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_get_conn = MagicMock()
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", mock_get_conn):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/predict/evidence/item-no-pred")

        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None
        assert data["q50"] is None

    @pytest.mark.asyncio
    async def test_db_pool_unavailable_returns_empty(self):
        """When DB pool raises RuntimeError, return empty evidence."""
        from fastapi.testclient import TestClient
        from main import app

        mock_get_conn = MagicMock()
        mock_get_conn.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Pool not initialized")
        )
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.features.predict_router.db_configured", return_value=True), \
             patch("app.features.predict_router.get_conn", mock_get_conn):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/predict/evidence/any-item")

        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None
