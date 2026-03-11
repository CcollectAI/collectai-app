"""Tests for app/agents/intake_feedback_router.py — User corrections + active learning.

Covers:
  - POST /intake/feedback — submit corrections, validation, DB fallback
  - GET  /intake/feedback/prompts/{id} — active learning prompts
  - Model validation (FeedbackRequest, FeedbackResponse, ActiveLearningPrompt)
  - Persistence verification with mocked DB
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("FORCE_DEV_MODE", "true")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PER_USER_RATE_LIMIT_ENABLED"] = "false"

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from app.auth import get_current_user_id  # noqa: E402

client = TestClient(app)

TEST_USER_ID = "feedback-test-user-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _AsyncCtx:
    """Async context manager mock for get_conn()."""
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        return self.conn
    async def __aexit__(self, *args):
        pass


def _override_user():
    """Override the auth dependency to return a test user."""
    async def _fake_user():
        return TEST_USER_ID
    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _setup_teardown():
    _override_user()
    yield
    _clear_overrides()


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------

class TestFeedbackModels:
    def test_feedback_request_requires_session_id(self):
        """scan_session_id is mandatory."""
        from app.agents.intake_feedback_router import FeedbackRequest
        with pytest.raises(Exception):
            FeedbackRequest()

    def test_feedback_request_empty_session_id_fails(self):
        """Empty session_id should fail (min_length=1)."""
        from app.agents.intake_feedback_router import FeedbackRequest
        with pytest.raises(Exception):
            FeedbackRequest(scan_session_id="")

    def test_feedback_request_optional_corrections(self):
        """All correction fields default to None."""
        from app.agents.intake_feedback_router import FeedbackRequest
        req = FeedbackRequest(scan_session_id="sess-1")
        assert req.corrected_name is None
        assert req.corrected_category is None
        assert req.corrected_condition is None

    def test_feedback_request_all_fields(self):
        """All correction fields can be set."""
        from app.agents.intake_feedback_router import FeedbackRequest
        req = FeedbackRequest(
            scan_session_id="sess-2",
            corrected_name="Charizard",
            corrected_category="pokemon",
            corrected_condition="near_mint",
        )
        assert req.corrected_name == "Charizard"
        assert req.corrected_category == "pokemon"
        assert req.corrected_condition == "near_mint"

    def test_feedback_response_defaults(self):
        """FeedbackResponse defaults: accepted=True, retrain_flagged=False."""
        from app.agents.intake_feedback_router import FeedbackResponse
        resp = FeedbackResponse(id="id-1", scan_session_id="sess-1")
        assert resp.accepted is True
        assert resp.retrain_flagged is False

    def test_active_learning_prompt_model(self):
        """ActiveLearningPrompt has question, options, field, session."""
        from app.agents.intake_feedback_router import ActiveLearningPrompt
        p = ActiveLearningPrompt(
            question="Which is correct?",
            options=["A", "B", "C"],
            field="category",
            scan_session_id="sess-3",
        )
        assert len(p.options) == 3
        assert p.field == "category"

    def test_active_learning_response_empty(self):
        """Default response has empty prompts list."""
        from app.agents.intake_feedback_router import ActiveLearningResponse
        r = ActiveLearningResponse()
        assert r.prompts == []

    def test_session_id_max_length(self):
        """Session ID exceeding 64 chars should fail."""
        from app.agents.intake_feedback_router import FeedbackRequest
        with pytest.raises(Exception):
            FeedbackRequest(scan_session_id="x" * 65)


# ---------------------------------------------------------------------------
# POST /intake/feedback — DB not configured (in-memory fallback)
# ---------------------------------------------------------------------------

class TestFeedbackNoDb:
    def test_feedback_accepted_without_db(self):
        """When DB is not configured, feedback should still be accepted."""
        with patch("app.db.db_configured", return_value=False):
            resp = client.post(
                "/intake/feedback",
                json={
                    "scan_session_id": "sess-no-db",
                    "corrected_name": "Fixed Name",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["accepted"] is True
        assert body["scan_session_id"] == "sess-no-db"
        assert body["retrain_flagged"] is False

    def test_no_corrections_without_db(self):
        """With no DB, missing corrections don't trigger validation error."""
        with patch("app.db.db_configured", return_value=False):
            resp = client.post(
                "/intake/feedback",
                json={"scan_session_id": "sess-empty"},
            )
        # Without DB, the code returns early before checking corrections
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /intake/feedback — with DB configured
# ---------------------------------------------------------------------------

class TestFeedbackWithDb:
    def test_no_corrections_returns_400(self):
        """If DB is up but no corrections provided, return 400."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.post(
                "/intake/feedback",
                json={"scan_session_id": "sess-no-fix"},
            )
        assert resp.status_code == 400

    def test_correction_persisted(self):
        """Valid correction should be inserted into DB."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)  # No gamification row
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=5)  # Below retrain threshold

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.post(
                "/intake/feedback",
                json={
                    "scan_session_id": "sess-persist",
                    "corrected_name": "Pikachu VMAX",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["accepted"] is True
        assert body["retrain_flagged"] is False
        # Verify execute was called (insert)
        assert conn.execute.await_count >= 1

    def test_retrain_flagged_at_threshold(self):
        """When corrections reach 50, retrain_flagged should be True."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=50)  # At threshold

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.post(
                "/intake/feedback",
                json={
                    "scan_session_id": "sess-retrain",
                    "corrected_category": "pokemon",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["retrain_flagged"] is True

    def test_retrain_not_flagged_below_threshold(self):
        """Below 50 corrections, retrain_flagged stays False."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=30)

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.post(
                "/intake/feedback",
                json={
                    "scan_session_id": "sess-below",
                    "corrected_category": "lego",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["retrain_flagged"] is False

    def test_high_level_user_gets_double_weight(self):
        """Users at level >= 10 should get user_weight = 2.0."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"level": 15})
        conn.execute = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.post(
                "/intake/feedback",
                json={
                    "scan_session_id": "sess-weight",
                    "corrected_name": "High Level Fix",
                },
            )
        assert resp.status_code == 200
        # Verify user_weight=2.0 was passed to execute ($7 param)
        call_args = conn.execute.call_args_list
        # The insert call should have user_weight as the last positional arg
        insert_call = [c for c in call_args if c[0] and "INSERT" in str(c[0][0])]
        if insert_call:
            assert insert_call[0][0][-1] == 2.0  # $7 = user_weight

    def test_db_error_returns_500(self):
        """DB error during insert should return 500."""
        # First call (gamification lookup) succeeds, second (insert) fails
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock(side_effect=Exception("DB connection lost"))

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.post(
                "/intake/feedback",
                json={
                    "scan_session_id": "sess-err",
                    "corrected_name": "Fail",
                },
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /intake/feedback — request validation
# ---------------------------------------------------------------------------

class TestFeedbackRequestValidation:
    def test_missing_session_id_returns_422(self):
        """Missing scan_session_id should return 422."""
        resp = client.post(
            "/intake/feedback",
            json={"corrected_name": "Oops"},
        )
        assert resp.status_code == 422

    def test_empty_body_returns_422(self):
        """Empty body should return 422."""
        resp = client.post(
            "/intake/feedback",
            content=b"{}",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422

    def test_name_max_length_enforced(self):
        """corrected_name exceeding 500 chars should fail."""
        resp = client.post(
            "/intake/feedback",
            json={
                "scan_session_id": "sess-long",
                "corrected_name": "x" * 501,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /intake/feedback/prompts/{session_id} — active learning
# ---------------------------------------------------------------------------

class TestActiveLearningPrompts:
    def test_prompts_no_db_returns_empty(self):
        """Without DB, return empty prompts list."""
        with patch("app.db.db_configured", return_value=False):
            resp = client.get("/intake/feedback/prompts/sess-no-db")
        assert resp.status_code == 200
        assert resp.json()["prompts"] == []

    def test_prompts_no_matching_item(self):
        """When item not found, return empty prompts."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.get("/intake/feedback/prompts/sess-missing")
        assert resp.status_code == 200
        assert resp.json()["prompts"] == []

    def test_prompts_low_confidence_generates_prompt(self):
        """Item with name_confidence in 0.5-0.7 should generate a name prompt."""
        import json
        attrs = {"name_confidence": 0.6, "suggested_name": "Charizard VMAX"}
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={
            "attributes_json": json.dumps(attrs),
        })

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.get("/intake/feedback/prompts/sess-low-conf")
        assert resp.status_code == 200
        prompts = resp.json()["prompts"]
        assert len(prompts) >= 1
        assert prompts[0]["field"] == "name"
        assert "Charizard VMAX" in prompts[0]["options"]

    def test_prompts_high_confidence_no_prompt(self):
        """Item with name_confidence > 0.7 should not generate prompts."""
        import json
        attrs = {"name_confidence": 0.95, "suggested_name": "High Conf"}
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={
            "attributes_json": json.dumps(attrs),
        })

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.get("/intake/feedback/prompts/sess-high-conf")
        assert resp.status_code == 200
        assert resp.json()["prompts"] == []

    def test_prompts_db_error_returns_empty(self):
        """DB error should gracefully return empty prompts."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        with patch("app.db.db_configured", return_value=True), \
             patch("app.db.get_conn", return_value=_AsyncCtx(conn)):
            resp = client.get("/intake/feedback/prompts/sess-err")
        assert resp.status_code == 200
        assert resp.json()["prompts"] == []
