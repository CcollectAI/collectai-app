"""Tests for app/features/feedback_router.py — feedback submit and correction endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
DB calls are mocked where the pool would be non-None.
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

VALID_ITEM_ID = str(uuid4())


# ===========================================================================
# POST /feedback/submit — offline mode (no DB pool)
# ===========================================================================

class TestFeedbackSubmitOffline:
    def test_submit_sale_price_success(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "sale_price",
            "value": "49.99",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["message"] == "Feedback recorded (offline mode)"
        assert data["feedback_id"] is None

    def test_submit_disagree(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "disagree",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_submit_accurate(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "accurate",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_submit_custom_with_notes(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "custom",
            "value": "wrong_edition",
            "notes": "This is a 1st edition, not unlimited",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_submit_disagree_with_value(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "disagree",
            "value": "too_high",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_submit_accurate_with_value(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "accurate",
            "value": "spot_on",
        })
        assert r.status_code == 200

    # ---- Validation / error cases ----

    def test_submit_missing_item_id_422(self):
        r = client.post("/feedback/submit", json={
            "feedback_type": "sale_price",
        })
        assert r.status_code == 422

    def test_submit_missing_feedback_type_422(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
        })
        assert r.status_code == 422

    def test_submit_empty_body_422(self):
        r = client.post("/feedback/submit", json={})
        assert r.status_code == 422

    def test_submit_item_id_too_long_422(self):
        r = client.post("/feedback/submit", json={
            "item_id": "x" * 65,
            "feedback_type": "sale_price",
        })
        assert r.status_code == 422

    def test_submit_feedback_type_too_long_422(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "a" * 51,
        })
        assert r.status_code == 422

    def test_submit_value_too_long_422(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "sale_price",
            "value": "x" * 501,
        })
        assert r.status_code == 422

    def test_submit_notes_too_long_422(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "sale_price",
            "notes": "n" * 2001,
        })
        assert r.status_code == 422

    def test_submit_response_shape(self):
        r = client.post("/feedback/submit", json={
            "item_id": VALID_ITEM_ID,
            "feedback_type": "accurate",
        })
        data = r.json()
        assert "success" in data
        assert "feedback_id" in data
        assert "message" in data


# ===========================================================================
# POST /feedback/submit — with mocked DB pool
# ===========================================================================

class TestFeedbackSubmitWithDB:
    def _mock_pool(self):
        """Create a mock pool that returns a mock connection."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": str(uuid4())})

        mock_pool = MagicMock()
        mock_acquire = AsyncMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_acquire
        return mock_pool, mock_conn

    def test_submit_with_db_success(self):
        mock_pool, mock_conn = self._mock_pool()
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "sale_price",
                "value": "25.00",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["feedback_id"] is not None
        assert data["message"] == "Feedback submitted successfully"

    def test_submit_with_db_invalid_uuid_400(self):
        """Non-UUID item_id should return 400 when DB is available."""
        mock_pool, _mock_conn = self._mock_pool()
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/submit", json={
                "item_id": "not-a-uuid",
                "feedback_type": "sale_price",
                "value": "10.00",
            })
        assert r.status_code == 400
        assert "Invalid item_id" in r.json()["detail"]

    def test_submit_with_db_error_500(self):
        """Database errors should return 500."""
        mock_pool, mock_conn = self._mock_pool()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB connection lost"))
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "disagree",
            })
        assert r.status_code == 500


# ===========================================================================
# POST /feedback/correction — offline mode (no DB pool)
# ===========================================================================

class TestCorrectionSubmitOffline:
    def test_correction_offline_success(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_price": 99.99,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["message"] == "Correction recorded (offline mode)"

    def test_correction_offline_with_all_fields(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_price": 150.00,
            "corrected_condition": "Near Mint",
            "corrected_category": "pokemon",
            "corrected_attributes": {"edition": "1st Edition", "foil": True},
            "notes": "This is a first edition card",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_correction_offline_condition_only(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_condition": "Good",
        })
        assert r.status_code == 200

    def test_correction_offline_category_only(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_category": "mtg",
        })
        assert r.status_code == 200

    # ---- Validation / error cases ----

    def test_correction_missing_item_id_422(self):
        r = client.post("/feedback/correction", json={
            "corrected_price": 10.00,
        })
        assert r.status_code == 422

    def test_correction_empty_body_422(self):
        r = client.post("/feedback/correction", json={})
        assert r.status_code == 422

    def test_correction_item_id_too_long_422(self):
        r = client.post("/feedback/correction", json={
            "item_id": "x" * 65,
            "corrected_price": 10.00,
        })
        assert r.status_code == 422

    def test_correction_condition_too_long_422(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_condition": "c" * 101,
        })
        assert r.status_code == 422

    def test_correction_category_too_long_422(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_category": "c" * 65,
        })
        assert r.status_code == 422

    def test_correction_notes_too_long_422(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_price": 10.00,
            "notes": "n" * 2001,
        })
        assert r.status_code == 422

    def test_correction_response_shape(self):
        r = client.post("/feedback/correction", json={
            "item_id": VALID_ITEM_ID,
            "corrected_price": 42.00,
        })
        data = r.json()
        assert "success" in data
        assert "message" in data


# ===========================================================================
# POST /feedback/correction — with mocked DB pool
# ===========================================================================

class TestCorrectionSubmitWithDB:
    def _mock_pool(self, execute_result="UPDATE 1"):
        """Create a mock pool that returns a mock connection."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=execute_result)

        mock_pool = MagicMock()
        mock_acquire = AsyncMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_acquire
        return mock_pool, mock_conn

    def test_correction_with_db_success(self):
        mock_pool, mock_conn = self._mock_pool()
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 75.50,
                "notes": "Verified sale price",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["message"] == "Correction submitted successfully"

    def test_correction_with_db_not_found_404(self):
        """When UPDATE returns 0 rows, return 404."""
        mock_pool, _mock_conn = self._mock_pool(execute_result="UPDATE 0")
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 75.50,
            })
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_correction_with_db_no_fields_400(self):
        """When no correction fields are provided (only item_id), return 400."""
        mock_pool, _mock_conn = self._mock_pool()
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
            })
        assert r.status_code == 400
        assert "No correction fields" in r.json()["detail"]

    def test_correction_with_db_invalid_uuid_400(self):
        """Non-UUID item_id should return 400 when DB is available."""
        mock_pool, _mock_conn = self._mock_pool()
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/correction", json={
                "item_id": "not-a-uuid",
                "corrected_price": 10.00,
            })
        assert r.status_code == 400

    def test_correction_with_db_error_500(self):
        """Database errors should return 500."""
        mock_pool, mock_conn = self._mock_pool()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB timeout"))
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 10.00,
            })
        assert r.status_code == 500

    def test_correction_builds_correct_update_query(self):
        """Verify the dynamic query builder adds all fields."""
        mock_pool, mock_conn = self._mock_pool()
        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            r = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 100.00,
                "corrected_condition": "Mint",
                "corrected_category": "pokemon",
                "notes": "Test note",
            })
        assert r.status_code == 200
        # Verify execute was called (the UPDATE query should include all fields)
        assert mock_conn.execute.call_count >= 1
        args = mock_conn.execute.call_args_list[0]
        query = args[0][0]
        assert "corrected_price" in query
        assert "corrected_condition" in query
        assert "corrected_category" in query
        assert "correction_notes" in query
        assert "corrected_at" in query
