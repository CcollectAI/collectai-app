"""
Vision classifier for CollectAI.

Classifies collectible items from images using a 3-tier approach:
  Tier 1 (CLIP via fal.ai): Real image embeddings + zero-shot category matching
  Tier 2 (OpenAI Vision): GPT-4o-mini vision API for classification
  Tier 3 (Heuristic): Filename keywords, EXIF metadata, barcode detection

Returns a ClassificationResult with category, confidence, condition, and optional embeddings.

This module is the main orchestrator; implementation details live in sub-modules:
  - vision_helpers: shared types, constants, utilities
  - clip_predictor: CLIP embedding and pre-filtering
  - openai_vision: OpenAI Vision API calls and prompt construction
  - confidence_aggregator: heuristic fallback classification
"""

from __future__ import annotations

import logging

# Re-export public API so existing imports continue to work:
#   from app.ml.vision_classifier import classify_image
#   from app.ml.vision_classifier import ClassificationResult
#   from app.ml.vision_classifier import ALL_CATEGORIES, CATEGORY_DESCRIPTIONS
#   from app.ml.vision_classifier import FAL_KEY, OPENAI_API_KEY  (via config)
from app.config import FAL_KEY, OPENAI_API_KEY  # noqa: F401 — re-exported
from app.ml.vision_helpers import (  # noqa: F401 — re-exported
    ALL_CATEGORIES,
    CATEGORY_DESCRIPTIONS,
    CATEGORY_PROMPTS,
    CONDITION_KEYWORDS,
    ClassificationResult,
)
from app.ml.clip_predictor import classify_clip as _classify_clip
from app.ml.openai_vision import classify_openai_vision as _classify_openai_vision
from app.ml.confidence_aggregator import classify_heuristic as _classify_heuristic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def classify_image(
    image_bytes: bytes,
    filename: str = "",
) -> ClassificationResult:
    """
    Classify and identify a collectible item image using a refined 3-tier approach.

    Tier 1: CLIP via fal.ai — fast pre-filter to get a category_hint
    Tier 2: OpenAI Vision with category_hint — specific item identification
    Tier 3: Heuristic fallback (always available)

    CLIP now feeds INTO OpenAI Vision rather than being an alternative.
    This gives us fast category narrowing + precise item identification.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, or WebP)
        filename: Original filename (used for heuristic hints)

    Returns:
        ClassificationResult with category, confidence, and optional embeddings
    """
    if not image_bytes:
        logger.warning("classify_image called with empty image bytes")
        return ClassificationResult(
            category_id="funko",
            category_confidence=0.0,
            classification_method="heuristic",
            model_version="heuristic:v1",
            attributes={"error": "empty_image"},
        )

    # Tier 1: CLIP — fast pre-filter for category hint
    category_hint: str | None = None
    clip_embedding: list[float] | None = None
    clip_result = await _classify_clip(image_bytes, filename)
    if clip_result is not None and clip_result.category_confidence > 0.5:
        category_hint = clip_result.category_id
        clip_embedding = clip_result.embedding_vector
        logger.info(
            "CLIP pre-filter: hint=%s (confidence=%.2f)",
            category_hint, clip_result.category_confidence,
        )

    # Tier 2: OpenAI Vision with category hint for specific identification
    result = await _classify_openai_vision(image_bytes, filename, category_hint)
    if result is not None:
        # Preserve CLIP embedding on the final result for future vector search
        if clip_embedding:
            result.embedding_vector = clip_embedding
            if category_hint:
                result.attributes["clip_hint"] = category_hint
                result.attributes["clip_confidence"] = clip_result.category_confidence
        return result

    # If CLIP returned a result on its own (even without OpenAI), use it
    if clip_result is not None:
        return clip_result

    # Tier 3: Heuristic (always returns a result)
    return _classify_heuristic(image_bytes, filename)
