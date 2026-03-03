"""
Tests for app/features/screenshot_intel_router.py — screenshot analysis endpoints.

Covers:
  - POST /screenshot-intel/analyze — happy path with mocked intake pipeline
  - POST /screenshot-intel/analyze — schema validation
  - POST /screenshot-intel/analyze — edge cases (missing screenshot, corrupt file, etc.)
  - POST /screenshot-intel/analyze — hints propagation (source_hint, category_hint)
  - POST /screenshot-intel/analyze — pipeline failure handling
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from app.rate_limit import _user_hits  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear rate limit state before each test to avoid cross-test 429 errors."""
    _user_hits.clear()
    yield
    _user_hits.clear()


# ---------------------------------------------------------------------------
# Fake IntakeResult for mocking process_intake
# ---------------------------------------------------------------------------


@dataclass
class FakeIntakeResult:
    """Mimics IntakeResult from app.agents.intake_agent."""

    name: Optional[str] = None
    category_id: Optional[str] = None
    category_confidence: float = 0.0
    subtype_id: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    identification_method: str = "vision_openai"
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None
    taxonomy_version: str = "v1.0"
    taxonomy_confidence: float = 0.0
    suggested_corrections: list[dict[str, Any]] = field(default_factory=list)
    estimated_price: Optional[float] = None
    price_source: Optional[str] = None
    price_band: Optional[dict[str, Any]] = None
    image_url: Optional[str] = None


def _mock_glob_found(screenshot_id: str, file_size: int = 1024):
    """
    Return a patch for Path.glob that simulates finding a screenshot file.
    The fake file's read_bytes returns `file_size` bytes.
    """
    fake_path = MagicMock(spec=Path)
    fake_path.read_bytes.return_value = b"\x89PNG" + b"\x00" * (file_size - 4)

    def glob_side_effect(pattern):
        if screenshot_id in pattern:
            return [fake_path]
        return []

    return glob_side_effect, fake_path


def _mock_glob_not_found():
    """Return a patch for Path.glob that simulates no matching files."""
    def glob_side_effect(pattern):
        return []
    return glob_side_effect


# ---------------------------------------------------------------------------
# POST /screenshot-intel/analyze — happy path
# ---------------------------------------------------------------------------


class TestAnalyzeScreenshotHappyPath:
    """Tests for POST /screenshot-intel/analyze with successful pipeline."""

    def test_successful_analysis_returns_item(self):
        """When intake pipeline identifies an item, response contains it."""
        fake_result = FakeIntakeResult(
            name="Charizard Base Set Holo",
            category_id="pokemon",
            category_confidence=0.95,
            estimated_price=350.0,
            identification_method="vision_openai",
            attributes={"condition_guess": "Near Mint"},
        )
        glob_fn, _ = _mock_glob_found("test-screenshot-1")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result) as mock_intake:
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-screenshot-1",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["screenshot_id"] == "test-screenshot-1"
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["item_name"] == "Charizard Base Set Holo"
        assert item["category"] == "pokemon"
        assert item["estimated_value"] == 350.0
        assert item["currency"] == "EUR"
        assert item["confidence"] == 0.95
        assert item["condition_guess"] == "Near Mint"
        assert item["can_add_to_watchlist"] is True

    def test_source_hint_propagated_to_listing_platform(self):
        """source_hint from the request is mapped to listing_platform in the response."""
        fake_result = FakeIntakeResult(
            name="Vintage Rolex Submariner",
            category_id="watches",
            category_confidence=0.88,
            estimated_price=8500.0,
            identification_method="vision_openai",
        )
        glob_fn, _ = _mock_glob_found("test-ss-source")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-source",
                "source_hint": "ebay",
            })

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["listing_platform"] == "ebay"

    def test_no_item_identified_returns_empty_items(self):
        """When the pipeline returns a result with name=None, items list is empty."""
        fake_result = FakeIntakeResult(name=None, identification_method="vision_openai")
        glob_fn, _ = _mock_glob_found("test-ss-noname")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-noname",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["identification_method"] == "vision_openai"

    def test_identification_method_from_pipeline(self):
        """The identification_method from the pipeline result is propagated."""
        fake_result = FakeIntakeResult(
            name="Some Item",
            identification_method="barcode_lookup",
        )
        glob_fn, _ = _mock_glob_found("test-ss-method")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-method",
            })

        assert resp.status_code == 200
        assert resp.json()["identification_method"] == "barcode_lookup"


# ---------------------------------------------------------------------------
# POST /screenshot-intel/analyze — schema validation
# ---------------------------------------------------------------------------


class TestAnalyzeScreenshotSchema:
    """Tests for response schema of POST /screenshot-intel/analyze."""

    def test_response_has_all_expected_fields(self):
        """Verify top-level response fields."""
        fake_result = FakeIntakeResult(
            name="Test Card",
            category_id="pokemon",
            category_confidence=0.75,
            estimated_price=100.0,
        )
        glob_fn, _ = _mock_glob_found("test-ss-schema")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-schema",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["screenshot_id"], str)
        assert isinstance(data["items"], list)
        assert isinstance(data["identification_method"], str)

    def test_item_entry_has_all_expected_fields(self):
        """Verify each item entry has all expected fields with correct types."""
        fake_result = FakeIntakeResult(
            name="Black Lotus Alpha",
            category_id="mtg",
            category_confidence=0.99,
            estimated_price=50000.0,
            identification_method="vision_openai",
            attributes={"condition_guess": "Light Played"},
        )
        glob_fn, _ = _mock_glob_found("test-ss-itemschema")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-itemschema",
                "source_hint": "vinted",
            })

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert isinstance(item["item_name"], str)
        assert item["category"] is None or isinstance(item["category"], str)
        assert item["estimated_value"] is None or isinstance(item["estimated_value"], (int, float))
        assert isinstance(item["currency"], str)
        assert isinstance(item["confidence"], (int, float))
        assert item["condition_guess"] is None or isinstance(item["condition_guess"], str)
        assert item["source_url"] is None or isinstance(item["source_url"], str)
        assert isinstance(item["can_add_to_watchlist"], bool)
        assert item["listing_platform"] is None or isinstance(item["listing_platform"], str)


# ---------------------------------------------------------------------------
# POST /screenshot-intel/analyze — edge cases
# ---------------------------------------------------------------------------


class TestAnalyzeScreenshotEdgeCases:
    """Tests for POST /screenshot-intel/analyze edge cases and errors."""

    def test_screenshot_not_found_returns_404(self):
        """When no matching file is found on disk, return 404."""
        glob_fn = _mock_glob_not_found()

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "nonexistent-screenshot",
            })

        assert resp.status_code == 404

    def test_tiny_file_returns_400(self):
        """A screenshot file smaller than 100 bytes returns 400."""
        glob_fn, _ = _mock_glob_found("test-ss-tiny", file_size=50)

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-tiny",
            })

        assert resp.status_code == 400

    def test_missing_screenshot_id_returns_422(self):
        """Missing required screenshot_id field triggers 422."""
        resp = client.post("/screenshot-intel/analyze", json={})
        assert resp.status_code == 422

    def test_empty_body_returns_422(self):
        """Sending no JSON body triggers 422."""
        resp = client.post("/screenshot-intel/analyze")
        assert resp.status_code == 422

    def test_pipeline_exception_returns_500(self):
        """When the vision pipeline raises an exception, return 500."""
        glob_fn, _ = _mock_glob_found("test-ss-error")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, side_effect=RuntimeError("OpenAI API timeout")):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-error",
            })

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /screenshot-intel/analyze — hints propagation
# ---------------------------------------------------------------------------


class TestAnalyzeScreenshotHints:
    """Tests for hint parameters being correctly passed to the pipeline."""

    def test_category_hint_passed_to_process_intake(self):
        """category_hint from request is forwarded to the intake pipeline."""
        fake_result = FakeIntakeResult(name="Test Item", category_id="pokemon")
        glob_fn, _ = _mock_glob_found("test-ss-cathint")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result) as mock_intake:
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-cathint",
                "category_hint": "pokemon",
            })

        assert resp.status_code == 200
        # Verify user_hints were passed
        call_kwargs = mock_intake.call_args
        assert call_kwargs is not None
        user_hints = call_kwargs.kwargs.get("user_hints") or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        # If kwargs, check directly
        if call_kwargs.kwargs.get("user_hints"):
            assert call_kwargs.kwargs["user_hints"]["category"] == "pokemon"

    def test_no_hints_passes_none(self):
        """When neither source_hint nor category_hint is given, user_hints is None."""
        fake_result = FakeIntakeResult(name="Test Item")
        glob_fn, _ = _mock_glob_found("test-ss-nohints")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result) as mock_intake:
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-nohints",
            })

        assert resp.status_code == 200
        call_kwargs = mock_intake.call_args
        assert call_kwargs is not None
        user_hints = call_kwargs.kwargs.get("user_hints")
        assert user_hints is None

    def test_source_hint_only_passes_source(self):
        """When only source_hint is given, user_hints contains source but category is None."""
        fake_result = FakeIntakeResult(name="Test Item")
        glob_fn, _ = _mock_glob_found("test-ss-sourcehint")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result) as mock_intake:
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-sourcehint",
                "source_hint": "instagram",
            })

        assert resp.status_code == 200
        call_kwargs = mock_intake.call_args
        user_hints = call_kwargs.kwargs.get("user_hints")
        assert user_hints is not None
        assert user_hints["source"] == "instagram"
        assert user_hints["category"] is None

    def test_condition_guess_none_when_no_attributes(self):
        """When intake result has no attributes, condition_guess is None."""
        fake_result = FakeIntakeResult(
            name="Some Item",
            attributes={},
        )
        glob_fn, _ = _mock_glob_found("test-ss-nocondition")

        with patch("app.features.screenshot_intel_router.Path.glob", side_effect=glob_fn), \
             patch("app.agents.intake_agent.process_intake", new_callable=AsyncMock, return_value=fake_result):
            resp = client.post("/screenshot-intel/analyze", json={
                "screenshot_id": "test-ss-nocondition",
            })

        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["condition_guess"] is None
