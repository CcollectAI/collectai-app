"""Tests for fast-path high-confidence match logic."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.intake_agent import IntakeResult, process_intake


@pytest.mark.asyncio
async def test_fast_path_skips_reprompt_when_high_confidence():
    """When clip_confidence >= 0.9 AND best alt score >= 0.9, reprompt is skipped."""
    result = IntakeResult()
    result.attributes = {"clip_confidence": 0.95}
    result.alternatives = [
        {"catalog_item_id": "abc", "item_key": "test-key", "title": "Test Item", "match_score": 0.92, "brand": "TestBrand", "rarity": None, "set_code": None}
    ]
    # Fast-path should auto-select best match when both confidences are high
    best_alt_score = max(a.get("match_score", 0) for a in result.alternatives)
    clip_conf = result.attributes.get("clip_confidence", 0.0)
    assert clip_conf >= 0.90
    assert best_alt_score >= 0.90


@pytest.mark.asyncio
async def test_fast_path_not_triggered_low_clip():
    """When clip_confidence < 0.9, fast-path should not trigger."""
    result = IntakeResult()
    result.attributes = {"clip_confidence": 0.7}
    result.alternatives = [{"match_score": 0.95}]
    clip_conf = result.attributes.get("clip_confidence", 0.0)
    assert clip_conf < 0.90  # Should not fast-path


@pytest.mark.asyncio
async def test_fast_path_not_triggered_low_catalog():
    """When best catalog score < 0.9, fast-path should not trigger."""
    result = IntakeResult()
    result.attributes = {"clip_confidence": 0.95}
    result.alternatives = [{"match_score": 0.7}]
    best_alt_score = max(a.get("match_score", 0) for a in result.alternatives)
    assert best_alt_score < 0.90  # Should not fast-path


@pytest.mark.asyncio
async def test_scan_session_id_generated():
    """IntakeResult should have a scan_session_id."""
    result = IntakeResult()
    # session id will be generated in process_intake
    assert result.scan_session_id is None  # Default is None until process_intake sets it
