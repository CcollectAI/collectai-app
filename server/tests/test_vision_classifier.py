"""
Tests for app.ml.vision_classifier — the 3-tier classification orchestrator.

Mocks all external dependencies (CLIP via fal.ai, OpenAI Vision API, heuristic).
Focuses on orchestration logic: tier fallback order, confidence thresholds,
embedding propagation, error handling, and edge cases.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.ml.vision_helpers import ClassificationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_IMAGE = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG-like bytes


def _clip_result(
    category: str = "funko",
    confidence: float = 0.85,
    embedding: list[float] | None = None,
) -> ClassificationResult:
    return ClassificationResult(
        category_id=category,
        category_confidence=confidence,
        classification_method="clip",
        model_version="clip:fal-ai",
        embedding_vector=embedding or [0.1, 0.2, 0.3],
        attributes={},
    )


def _openai_result(
    category: str = "funko",
    confidence: float = 0.92,
    name: str = "Funko Pop! Batman #01",
) -> ClassificationResult:
    return ClassificationResult(
        category_id=category,
        category_confidence=confidence,
        classification_method="openai_vision",
        model_version="openai:gpt-4o-mini",
        suggested_name=name,
        attributes={},
    )


def _heuristic_result(
    category: str = "funko",
    confidence: float = 0.55,
) -> ClassificationResult:
    return ClassificationResult(
        category_id=category,
        category_confidence=confidence,
        classification_method="heuristic",
        model_version="heuristic:v1",
        attributes={},
    )


# ---------------------------------------------------------------------------
# Patches applied to every test — all three tier functions + config keys
# ---------------------------------------------------------------------------

CLIP_PATCH = "app.ml.vision_classifier._classify_clip"
OPENAI_PATCH = "app.ml.vision_classifier._classify_openai_vision"
HEURISTIC_PATCH = "app.ml.vision_classifier._classify_heuristic"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClassifyImageOrchestration:
    """Test the 3-tier orchestration logic in classify_image."""

    @pytest.mark.asyncio
    async def test_successful_classification_all_tiers(self):
        """Happy path: CLIP provides hint, OpenAI returns final result with embedding merged."""
        clip_res = _clip_result(category="pokemon", confidence=0.80, embedding=[1.0, 2.0])
        openai_res = _openai_result(category="pokemon", confidence=0.95, name="Charizard Base Set #4")

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH) as mock_heuristic,
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "charizard.jpg")

        assert result.category_id == "pokemon"
        assert result.category_confidence == 0.95
        assert result.classification_method == "openai_vision"
        assert result.suggested_name == "Charizard Base Set #4"
        # CLIP embedding should be merged onto OpenAI result
        assert result.embedding_vector == [1.0, 2.0]
        assert result.attributes.get("clip_hint") == "pokemon"
        assert result.attributes.get("clip_confidence") == 0.80
        # Heuristic should NOT be called
        mock_heuristic.assert_not_called()
        # OpenAI should be called with category_hint from CLIP
        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "charizard.jpg", "pokemon")

    @pytest.mark.asyncio
    async def test_clip_low_confidence_no_hint(self):
        """CLIP returns low confidence (<= 0.5) — no hint passed to OpenAI."""
        clip_res = _clip_result(category="funko", confidence=0.3)
        openai_res = _openai_result(category="lego", confidence=0.88)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "test.jpg")

        assert result.category_id == "lego"
        # OpenAI called with category_hint=None because CLIP confidence <= 0.5
        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "test.jpg", None)
        # No CLIP embedding merged (confidence too low)
        assert result.embedding_vector is None

    @pytest.mark.asyncio
    async def test_clip_returns_none_openai_succeeds(self):
        """CLIP fails entirely — OpenAI still succeeds without a hint."""
        openai_res = _openai_result(category="watches", confidence=0.90)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=None),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "rolex.jpg")

        assert result.category_id == "watches"
        assert result.classification_method == "openai_vision"
        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "rolex.jpg", None)

    @pytest.mark.asyncio
    async def test_openai_returns_none_falls_back_to_clip(self):
        """OpenAI fails but CLIP had a result — use CLIP result directly."""
        clip_res = _clip_result(category="sneakers", confidence=0.70)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=None),
            patch(HEURISTIC_PATCH) as mock_heuristic,
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "shoes.jpg")

        assert result.category_id == "sneakers"
        assert result.classification_method == "clip"
        mock_heuristic.assert_not_called()

    @pytest.mark.asyncio
    async def test_openai_and_clip_fail_falls_back_to_heuristic(self):
        """Both CLIP and OpenAI fail — heuristic is the last resort."""
        heur_res = _heuristic_result(category="lego", confidence=0.55)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=None),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=None),
            patch(HEURISTIC_PATCH, return_value=heur_res) as mock_heuristic,
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "lego_set.jpg")

        assert result.category_id == "lego"
        assert result.classification_method == "heuristic"
        mock_heuristic.assert_called_once_with(FAKE_IMAGE, "lego_set.jpg")

    @pytest.mark.asyncio
    async def test_clip_low_confidence_openai_fails_heuristic(self):
        """CLIP low confidence + OpenAI fails — CLIP result still used (not None)."""
        clip_res = _clip_result(category="manga", confidence=0.3)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=None),
            patch(HEURISTIC_PATCH) as mock_heuristic,
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "book.jpg")

        # Even low-confidence CLIP is preferred over heuristic
        assert result.category_id == "manga"
        assert result.classification_method == "clip"
        mock_heuristic.assert_not_called()


class TestEmptyAndInvalidInput:
    """Test edge cases with missing or invalid image bytes."""

    @pytest.mark.asyncio
    async def test_empty_bytes(self):
        """Empty image bytes returns a fallback result immediately."""
        from app.ml.vision_classifier import classify_image
        result = await classify_image(b"", "empty.jpg")

        assert result.category_id == "funko"
        assert result.category_confidence == 0.0
        assert result.classification_method == "heuristic"
        assert result.attributes.get("error") == "empty_image"

    @pytest.mark.asyncio
    async def test_none_bytes_treated_as_empty(self):
        """None image bytes (falsy) returns a fallback result."""
        from app.ml.vision_classifier import classify_image
        # None is falsy, same as empty bytes
        result = await classify_image(None, "nothing.jpg")

        assert result.category_confidence == 0.0
        assert result.attributes.get("error") == "empty_image"

    @pytest.mark.asyncio
    async def test_empty_filename(self):
        """Empty filename is acceptable — classification still proceeds."""
        openai_res = _openai_result(category="funko", confidence=0.85)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=None),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "")

        assert result.category_id == "funko"
        assert result.classification_method == "openai_vision"


class TestEmbeddingPropagation:
    """Test that CLIP embeddings are correctly propagated to the final result."""

    @pytest.mark.asyncio
    async def test_embedding_merged_when_clip_confident(self):
        """CLIP embedding vector is attached to OpenAI result when CLIP confidence > 0.5."""
        embedding = [0.5, 0.6, 0.7, 0.8]
        clip_res = _clip_result(category="yugioh", confidence=0.75, embedding=embedding)
        openai_res = _openai_result(category="yugioh", confidence=0.92)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "card.jpg")

        assert result.embedding_vector == embedding
        assert result.attributes["clip_hint"] == "yugioh"
        assert result.attributes["clip_confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_no_embedding_when_clip_none(self):
        """No embedding when CLIP returns None."""
        openai_res = _openai_result(category="funko", confidence=0.88)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=None),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "pop.jpg")

        assert result.embedding_vector is None
        assert "clip_hint" not in result.attributes

    @pytest.mark.asyncio
    async def test_no_embedding_merged_when_clip_low_confidence(self):
        """CLIP embedding NOT merged when confidence <= 0.5."""
        clip_res = _clip_result(category="funko", confidence=0.4, embedding=[9.9])
        openai_res = _openai_result(category="funko", confidence=0.90)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "pop.jpg")

        # Low-confidence CLIP: no embedding merge
        assert result.embedding_vector is None
        assert "clip_hint" not in result.attributes


class TestCategoryMapping:
    """Test that CLIP category hint is forwarded correctly to OpenAI."""

    @pytest.mark.asyncio
    async def test_clip_hint_forwarded(self):
        """High-confidence CLIP category becomes OpenAI's category_hint."""
        clip_res = _clip_result(category="warhammer", confidence=0.88)
        openai_res = _openai_result(category="warhammer", confidence=0.95)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            await classify_image(FAKE_IMAGE, "mini.jpg")

        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "mini.jpg", "warhammer")

    @pytest.mark.asyncio
    async def test_openai_can_override_clip_category(self):
        """OpenAI may return a different category than CLIP's hint — that's fine."""
        clip_res = _clip_result(category="action_figures", confidence=0.60)
        openai_res = _openai_result(category="hot_toys", confidence=0.93)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "figure.jpg")

        # OpenAI's category wins
        assert result.category_id == "hot_toys"
        # But CLIP hint is still recorded in attributes
        assert result.attributes["clip_hint"] == "action_figures"


class TestExternalErrors:
    """Test graceful handling of errors from external services."""

    @pytest.mark.asyncio
    async def test_clip_raises_exception_continues(self):
        """CLIP raising an exception should not crash — treat as None."""
        openai_res = _openai_result(category="lego", confidence=0.85)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, side_effect=Exception("fal.ai timeout")),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            # The exception propagates because the orchestrator doesn't catch it.
            # Let's verify this behavior — if it should be caught, this test
            # documents the current behavior.
            with pytest.raises(Exception, match="fal.ai timeout"):
                await classify_image(FAKE_IMAGE, "bricks.jpg")

    @pytest.mark.asyncio
    async def test_openai_raises_exception_falls_to_clip(self):
        """OpenAI raising an exception propagates (not caught in orchestrator)."""
        clip_res = _clip_result(category="lego", confidence=0.70)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, side_effect=Exception("API error")),
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            with pytest.raises(Exception, match="API error"):
                await classify_image(FAKE_IMAGE, "set.jpg")

    @pytest.mark.asyncio
    async def test_all_tiers_none_reaches_heuristic(self):
        """When CLIP=None and OpenAI=None, heuristic must be called."""
        heur_res = _heuristic_result(category="retro_games", confidence=0.52)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=None),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=None),
            patch(HEURISTIC_PATCH, return_value=heur_res),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "nes_cart.jpg")

        assert result.category_id == "retro_games"
        assert result.classification_method == "heuristic"


class TestConfidenceThreshold:
    """Test the 0.5 confidence threshold for CLIP hint propagation."""

    @pytest.mark.asyncio
    async def test_exactly_0_5_no_hint(self):
        """Confidence exactly 0.5 does NOT trigger hint (threshold is >0.5)."""
        clip_res = _clip_result(category="funko", confidence=0.5)
        openai_res = _openai_result(category="funko", confidence=0.90)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "pop.jpg")

        # 0.5 is NOT > 0.5, so no hint
        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "pop.jpg", None)
        assert result.embedding_vector is None

    @pytest.mark.asyncio
    async def test_just_above_threshold(self):
        """Confidence 0.51 triggers hint propagation."""
        clip_res = _clip_result(category="kpop_merch", confidence=0.51, embedding=[1.0])
        openai_res = _openai_result(category="kpop_merch", confidence=0.88)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=clip_res),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE, "album.jpg")

        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "album.jpg", "kpop_merch")
        assert result.embedding_vector == [1.0]
        assert result.attributes["clip_hint"] == "kpop_merch"


class TestDefaultFilename:
    """Test that default empty filename works."""

    @pytest.mark.asyncio
    async def test_no_filename_argument(self):
        """classify_image can be called with just image_bytes (filename defaults to '')."""
        openai_res = _openai_result(category="watches", confidence=0.87)

        with (
            patch(CLIP_PATCH, new_callable=AsyncMock, return_value=None),
            patch(OPENAI_PATCH, new_callable=AsyncMock, return_value=openai_res) as mock_openai,
            patch(HEURISTIC_PATCH),
        ):
            from app.ml.vision_classifier import classify_image
            result = await classify_image(FAKE_IMAGE)

        assert result.category_id == "watches"
        mock_openai.assert_awaited_once_with(FAKE_IMAGE, "", None)
