"""Tests for predict_router — /predict/evidence/{item_id}."""

import os
import pytest
from fastapi.testclient import TestClient

# Force DB-disabled mode for tests
os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DB_DSN", "")
os.environ.setdefault("DEV_MODE", "true")

from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


class TestPriceEvidence:
    """GET /predict/evidence/{item_id}."""

    def test_returns_empty_when_db_disabled(self):
        """With DB disabled, the endpoint should return an empty evidence response."""
        resp = client.get("/predict/evidence/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] is None
        assert data["evidence_hit_ids"] == []
        assert data["prediction_at"] is None

    def test_returns_200_for_any_item_id(self):
        resp = client.get("/predict/evidence/some-item-id")
        assert resp.status_code == 200

    def test_response_schema(self):
        resp = client.get("/predict/evidence/test-item")
        data = resp.json()
        assert "explanation" in data
        assert "evidence_summary" in data
        assert "evidence_hit_ids" in data
        assert "prediction_at" in data
        assert "q10" in data
        assert "q50" in data
        assert "q90" in data
        assert "confidence_score" in data


class TestPriceTrend:
    """GET /predict/trend/{item_id}."""

    def test_returns_empty_when_db_disabled(self):
        resp = client.get("/predict/trend/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_points"] == []
        assert data["direction"] is None
        assert data["pct_change"] is None

    def test_response_schema(self):
        resp = client.get("/predict/trend/test-item")
        data = resp.json()
        assert "item_ref" in data
        assert "period_days" in data
        assert "data_points" in data
        assert "direction" in data
        assert "pct_change" in data
        assert "current_q50" in data
        assert "earliest_q50" in data

    def test_custom_period_days(self):
        resp = client.get("/predict/trend/test-item?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 30

    def test_invalid_days_rejected(self):
        resp = client.get("/predict/trend/test-item?days=3")
        assert resp.status_code == 422  # Below ge=7

    def test_max_days_rejected(self):
        resp = client.get("/predict/trend/test-item?days=999")
        assert resp.status_code == 422  # Above le=365
