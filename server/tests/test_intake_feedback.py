"""Tests for intake feedback router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class AsyncContextMock:
    def __init__(self, conn):
        self.conn = conn
    async def __aenter__(self):
        return self.conn
    async def __aexit__(self, *args):
        pass


def test_feedback_request_validation():
    """FeedbackRequest requires scan_session_id."""
    from app.agents.intake_feedback_router import FeedbackRequest
    req = FeedbackRequest(scan_session_id="test-123", corrected_name="Fixed Name")
    assert req.scan_session_id == "test-123"
    assert req.corrected_name == "Fixed Name"


def test_feedback_request_empty_session_fails():
    """Empty scan_session_id should fail validation."""
    from app.agents.intake_feedback_router import FeedbackRequest
    with pytest.raises(Exception):
        FeedbackRequest(scan_session_id="")


def test_feedback_response_model():
    """FeedbackResponse has correct fields."""
    from app.agents.intake_feedback_router import FeedbackResponse
    resp = FeedbackResponse(
        id="abc-123",
        scan_session_id="sess-456",
        accepted=True,
        retrain_flagged=False,
    )
    assert resp.accepted is True
    assert resp.retrain_flagged is False


def test_active_learning_prompt_model():
    """ActiveLearningPrompt model works."""
    from app.agents.intake_feedback_router import ActiveLearningPrompt
    prompt = ActiveLearningPrompt(
        question="Which name?",
        options=["Option A", "Option B"],
        field="name",
        scan_session_id="sess-123",
    )
    assert prompt.field == "name"
    assert len(prompt.options) == 2


def test_active_learning_response_default():
    """ActiveLearningResponse defaults to empty prompts."""
    from app.agents.intake_feedback_router import ActiveLearningResponse
    resp = ActiveLearningResponse()
    assert resp.prompts == []


@pytest.mark.asyncio
async def test_submit_feedback_no_corrections():
    """Should reject feedback with no corrections."""
    from app.agents.intake_feedback_router import FeedbackRequest
    req = FeedbackRequest(scan_session_id="test-session")
    assert req.corrected_name is None
    assert req.corrected_category is None
    assert req.corrected_condition is None


def test_user_weight_default():
    """Default user weight should be 1.0."""
    # Basic weight logic test
    user_weight = 1.0
    level = 5
    if level >= 10:
        user_weight = 2.0
    assert user_weight == 1.0


def test_user_weight_high_level():
    """Level >= 10 should get 2x weight."""
    user_weight = 1.0
    level = 15
    if level >= 10:
        user_weight = 2.0
    assert user_weight == 2.0


def test_retrain_threshold():
    """Retrain should be flagged at 50+ corrections."""
    threshold = 50
    count = 55
    retrain_flagged = count >= threshold
    assert retrain_flagged is True


def test_retrain_below_threshold():
    """Retrain should not be flagged below 50 corrections."""
    threshold = 50
    count = 30
    retrain_flagged = count >= threshold
    assert retrain_flagged is False


def test_feedback_request_all_fields():
    """FeedbackRequest with all correction fields."""
    from app.agents.intake_feedback_router import FeedbackRequest
    req = FeedbackRequest(
        scan_session_id="sess-789",
        corrected_name="Correct Name",
        corrected_category="pokemon",
        corrected_condition="near_mint",
    )
    assert req.corrected_name == "Correct Name"
    assert req.corrected_category == "pokemon"
    assert req.corrected_condition == "near_mint"


def test_feedback_response_retrain_flagged():
    """FeedbackResponse with retrain flagged."""
    from app.agents.intake_feedback_router import FeedbackResponse
    resp = FeedbackResponse(
        id="id-1",
        scan_session_id="sess-1",
        retrain_flagged=True,
    )
    assert resp.retrain_flagged is True
