"""Tests for app/features/quickscan_advanced_router.py — quickscan endpoints.

The quickscan router attempts to use ML models for price prediction.
Without a model loaded, it returns 422 for /single and fallback for /batch.
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
# POST /quickscan-advanced/single — single item scan
# ---------------------------------------------------------------------------

class TestQuickScanSingle:
    def test_single_scan_no_model(self):
        """Returns 422 when no ML model available for the category."""
        resp = client.post(
            "/quickscan-advanced/single",
            json={"category": "pokemon_tcg"},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    def test_single_scan_with_attributes(self):
        """Accepts optional attributes; still 422 without model."""
        resp = client.post(
            "/quickscan-advanced/single",
            json={
                "category": "funko",
                "edition_guess": "Chase",
                "condition_guess": "Mint",
                "rarity_score": 0.8,
            },
        )
        assert resp.status_code == 422

    def test_single_scan_no_body(self):
        """Returns 422 when request body is missing."""
        resp = client.post("/quickscan-advanced/single")
        assert resp.status_code == 422

    def test_single_scan_missing_category(self):
        """Returns 422 when category field is missing."""
        resp = client.post(
            "/quickscan-advanced/single",
            json={"edition_guess": "First Edition"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /quickscan-advanced/batch — batch scan
# ---------------------------------------------------------------------------

class TestQuickScanBatch:
    def test_batch_scan_returns_200(self):
        """Returns 200 with results for each image_id."""
        resp = client.post(
            "/quickscan-advanced/batch",
            json={
                "image_ids": ["img-001", "img-002"],
                "category": "funko",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2

    def test_batch_scan_empty_images(self):
        """Returns 200 with empty results for empty image list."""
        resp = client.post(
            "/quickscan-advanced/batch",
            json={"image_ids": [], "category": "lego"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    def test_batch_scan_no_model_returns_zero_confidence(self):
        """Without a model, batch results have confidence=0 and zero prices."""
        resp = client.post(
            "/quickscan-advanced/batch",
            json={"image_ids": ["img-001"], "category": "funko"},
        )
        assert resp.status_code == 200
        result = resp.json()["results"][0]
        assert result["prediction"]["confidence"] == 0.0
        assert result["prediction"]["estimated_mid"] == 0.0

    def test_batch_scan_missing_image_ids(self):
        """Returns 422 when image_ids field is missing."""
        resp = client.post(
            "/quickscan-advanced/batch",
            json={"category": "funko"},
        )
        assert resp.status_code == 422

    def test_batch_scan_no_body(self):
        """Returns 422 when request body is missing."""
        resp = client.post("/quickscan-advanced/batch")
        assert resp.status_code == 422

    def test_batch_scan_result_structure(self):
        """Each result has item_id, attributes, and prediction."""
        resp = client.post(
            "/quickscan-advanced/batch",
            json={"image_ids": ["img-001"], "category": "pokemon_tcg"},
        )
        assert resp.status_code == 200
        result = resp.json()["results"][0]
        assert "item_id" in result
        assert "attributes" in result
        assert "prediction" in result
        assert "category" in result["attributes"]
        assert "estimated_low" in result["prediction"]
        assert "estimated_mid" in result["prediction"]
        assert "estimated_high" in result["prediction"]
        assert "currency" in result["prediction"]
        assert "confidence" in result["prediction"]
