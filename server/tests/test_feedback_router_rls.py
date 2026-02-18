"""
Tests for app/features/feedback_router.py — RLS (ownership) fixes.

Separate from the existing test_feedback_router.py which covers offline mode and
basic DB mock scenarios. These tests specifically verify:
  - POST /feedback/submit — ownership check (item must belong to user)
  - POST /feedback/submit — item not found → 404
  - GET /feedback/corrections — scoped to user's corrections via taxonomy_corrections join
  - POST /feedback/correction — updates training item
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

VALID_ITEM_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_pool_with_conn():
    """Create a mock pool returning a mock connection via acquire()."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = mock_acquire
    return mock_pool, mock_conn


# ---------------------------------------------------------------------------
# POST /feedback/submit — ownership check
# ---------------------------------------------------------------------------


class TestFeedbackSubmitOwnership:
    """Tests for POST /feedback/submit with ownership verification."""

    def test_submit_with_ownership_check_success(self):
        """When item belongs to the user, feedback is accepted and saved."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        feedback_id = str(uuid4())

        # fetchval (ownership check) returns 1 => item exists for this user
        mock_conn.fetchval = AsyncMock(return_value=1)
        # fetchrow (INSERT RETURNING id) returns the new feedback row
        mock_conn.fetchrow = AsyncMock(return_value={"id": feedback_id})

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "sale_price",
                "value": "125.00",
                "notes": "Sold on eBay",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["feedback_id"] == feedback_id
        assert data["message"] == "Feedback submitted successfully"

        # Verify the ownership query was called
        assert mock_conn.fetchval.call_count >= 1
        ownership_query = mock_conn.fetchval.call_args[0][0]
        assert "user_id" in ownership_query
        assert "items" in ownership_query

    def test_submit_item_not_found_returns_404(self):
        """When item does not belong to user (fetchval returns None), return 404."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.fetchval = AsyncMock(return_value=None)

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "disagree",
            })

        assert resp.status_code == 404

    def test_submit_sale_price_logs_provenance_event(self):
        """When feedback_type=sale_price, a provenance event is auto-logged."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        feedback_id = str(uuid4())
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetchrow = AsyncMock(return_value={"id": feedback_id})
        mock_conn.execute = AsyncMock()

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "sale_price",
                "value": "200.00",
            })

        assert resp.status_code == 200
        # The provenance event INSERT should have been called via _log_provenance_event
        # (which acquires a second connection from the pool)
        assert mock_pool.acquire.call_count >= 2  # one for submit, one for provenance

    def test_submit_accurate_does_not_log_provenance(self):
        """When feedback_type=accurate, no provenance event is logged."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetchrow = AsyncMock(return_value={"id": str(uuid4())})

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "accurate",
            })

        assert resp.status_code == 200
        # Only one acquire call (the submit query), no provenance event
        assert mock_pool.acquire.call_count == 1

    def test_submit_label_format_sale_price(self):
        """Sale price feedback produces label 'sale_price:{value}'."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetchrow = AsyncMock(return_value={"id": str(uuid4())})

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "sale_price",
                "value": "42.50",
            })

        assert resp.status_code == 200
        # Verify the INSERT call included the correct label
        insert_call = mock_conn.fetchrow.call_args
        label_arg = insert_call[0][2]  # positional arg $2 = label
        assert label_arg == "sale_price:42.50"

    def test_submit_label_format_disagree(self):
        """Disagree feedback without value produces label 'disagree:inaccurate'."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetchrow = AsyncMock(return_value={"id": str(uuid4())})

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/submit", json={
                "item_id": VALID_ITEM_ID,
                "feedback_type": "disagree",
            })

        assert resp.status_code == 200
        insert_call = mock_conn.fetchrow.call_args
        label_arg = insert_call[0][2]
        assert label_arg == "disagree:inaccurate"


# ---------------------------------------------------------------------------
# GET /feedback/corrections — scoped to user
# ---------------------------------------------------------------------------


class TestListCorrectionsScoped:
    """Tests for GET /feedback/corrections — scoped to the current user."""

    def test_corrections_returns_user_scoped_results(self):
        """The query joins taxonomy_corrections on user_id to scope results."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": uuid4(),
                "corrected_price": 50.0,
                "corrected_condition": "Good",
                "corrected_category": "pokemon",
                "corrected_attributes": None,
                "correction_notes": "Corrected",
                "corrected_at": now,
            },
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.get("/feedback/corrections")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["corrections"]) == 1
        assert data["corrections"][0]["corrected_price"] == 50.0
        assert data["corrections"][0]["corrected_condition"] == "Good"

        # Verify the query includes user_id scoping via taxonomy_corrections
        fetch_call = mock_conn.fetch.call_args
        query = fetch_call[0][0]
        assert "taxonomy_corrections" in query
        assert "user_id" in query

    def test_corrections_empty_when_no_pool(self):
        """When pool is None (DB unavailable), return empty list."""
        with patch("app.features.feedback_router._get_db_pool", return_value=None):
            resp = client.get("/feedback/corrections")

        assert resp.status_code == 200
        assert resp.json()["corrections"] == []

    def test_corrections_pagination(self):
        """Pagination params (limit, offset) are passed through."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.get("/feedback/corrections?limit=10&offset=5")

        assert resp.status_code == 200
        # Verify pagination params were passed to the query
        fetch_call = mock_conn.fetch.call_args
        # limit=$1, offset=$2, user_id=$3
        assert fetch_call[0][1] == 10  # limit
        assert fetch_call[0][2] == 5   # offset

    def test_corrections_with_json_attributes(self):
        """Corrections with corrected_attributes as a JSON string are parsed."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": uuid4(),
                "corrected_price": None,
                "corrected_condition": None,
                "corrected_category": None,
                "corrected_attributes": '{"edition": "1st", "foil": true}',
                "correction_notes": None,
                "corrected_at": now,
            },
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.get("/feedback/corrections")

        assert resp.status_code == 200
        attrs = resp.json()["corrections"][0]["corrected_attributes"]
        assert attrs["edition"] == "1st"
        assert attrs["foil"] is True


# ---------------------------------------------------------------------------
# POST /feedback/correction — with ownership context
# ---------------------------------------------------------------------------


class TestCorrectionWithOwnership:
    """Tests for POST /feedback/correction with RLS-related behavior."""

    def test_correction_success_logs_taxonomy_correction(self):
        """When corrected_category is set, a taxonomy_corrections row is also inserted."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.fetchrow = AsyncMock(return_value={"category": "yugioh"})

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_category": "pokemon",
                "notes": "Was misclassified",
            })

        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify taxonomy_corrections INSERT was called
        execute_calls = mock_conn.execute.call_args_list
        # First call: UPDATE training_items, second call: INSERT taxonomy_corrections
        assert len(execute_calls) >= 2
        taxonomy_query = execute_calls[1][0][0]
        assert "taxonomy_corrections" in taxonomy_query
        assert "user_id" in taxonomy_query

    def test_correction_training_item_not_found_returns_404(self):
        """When UPDATE returns 0 rows, training item was not found → 404."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 99.99,
            })

        assert resp.status_code == 404

    def test_correction_no_fields_returns_400(self):
        """When no corrected fields are provided, return 400."""
        mock_pool, mock_conn = _mock_pool_with_conn()

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
            })

        assert resp.status_code == 400

    def test_correction_price_only(self):
        """Correcting only the price builds a minimal UPDATE query."""
        mock_pool, mock_conn = _mock_pool_with_conn()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.features.feedback_router._get_db_pool", return_value=mock_pool):
            resp = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 150.00,
            })

        assert resp.status_code == 200
        # Verify the UPDATE query was built correctly
        call = mock_conn.execute.call_args_list[0]
        query = call[0][0]
        assert "corrected_price" in query
        assert "corrected_at" in query
        # No taxonomy_corrections insert since corrected_category is not set
        assert mock_conn.execute.call_count == 1

    def test_correction_offline_mode(self):
        """When pool is None, return offline success without DB interaction."""
        with patch("app.features.feedback_router._get_db_pool", return_value=None):
            resp = client.post("/feedback/correction", json={
                "item_id": VALID_ITEM_ID,
                "corrected_price": 42.00,
            })

        assert resp.status_code == 200
        assert resp.json()["message"] == "Correction recorded (offline mode)"
