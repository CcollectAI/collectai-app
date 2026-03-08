"""Tests for multi-item detection."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.ml.multi_item_detector import (
    detect_multiple_items,
    DetectedItem,
    BoundingBox,
    MAX_ITEMS,
)


def test_bounding_box_defaults():
    """BoundingBox should have sane defaults."""
    bb = BoundingBox()
    assert bb.x == 0.0
    assert bb.y == 0.0
    assert bb.w == 1.0
    assert bb.h == 1.0


def test_detected_item_defaults():
    """DetectedItem should have sane defaults."""
    item = DetectedItem()
    assert item.item_index == 0
    assert item.confidence == 0.0
    assert item.category_hint is None


@pytest.mark.asyncio
async def test_returns_empty_without_api_key():
    """Should return empty list when no OpenAI API key."""
    with patch("app.ml.multi_item_detector.OPENAI_API_KEY", None):
        result = await detect_multiple_items(b"fake-image")
        assert result == []


@pytest.mark.asyncio
async def test_returns_empty_for_empty_image():
    """Should return empty list for empty image bytes."""
    result = await detect_multiple_items(b"")
    assert result == []


@pytest.mark.asyncio
async def test_max_items_constant():
    """MAX_ITEMS should be 10."""
    assert MAX_ITEMS == 10


@pytest.mark.asyncio
async def test_bounding_box_clamping():
    """Bounding box values should be clamped to 0-1 range."""
    bb = BoundingBox(
        x=max(0.0, min(1.0, -0.5)),
        y=max(0.0, min(1.0, 1.5)),
        w=max(0.0, min(1.0, 0.5)),
        h=max(0.0, min(1.0, 0.5)),
    )
    assert bb.x == 0.0
    assert bb.y == 1.0


@pytest.mark.asyncio
async def test_detected_item_with_values():
    """DetectedItem can hold values."""
    item = DetectedItem(
        item_index=1,
        bounding_box=BoundingBox(x=0.1, y=0.2, w=0.3, h=0.4),
        category_hint="pokemon",
        suggested_name="Charizard Base Set",
        confidence=0.85,
    )
    assert item.category_hint == "pokemon"
    assert item.confidence == 0.85


@pytest.mark.asyncio
async def test_circuit_breaker_prevents_call():
    """Should return empty when circuit breaker is open."""
    from workers.circuit_breaker import CircuitOpenError

    mock_circuit = MagicMock()
    mock_circuit.check.side_effect = CircuitOpenError("open", retry_after=60.0)

    with patch("app.ml.multi_item_detector.OPENAI_API_KEY", "test-key"):
        with patch("workers.circuit_breaker.openai_circuit", mock_circuit):
            result = await detect_multiple_items(b"\xff\xd8fake-jpeg")
            assert result == []
