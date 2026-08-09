"""
Vision classifier for CollectAI.

Classifies collectible items from images using a 2-tier approach:
  Tier 1 (OpenAI Vision): GPT-4o-mini vision API for identification
  Tier 2 (Heuristic): Filename keywords, EXIF metadata, barcode detection

Returns a ClassificationResult with category, confidence and condition.

This module is the main orchestrator; implementation details live in sub-modules:
  - vision_helpers: shared types, constants, utilities
  - openai_vision: OpenAI Vision API calls and prompt construction
  - confidence_aggregator: heuristic fallback classification

History: there used to be a Tier 1 "CLIP via fal.ai" pre-filter that produced a
`category_hint` for OpenAI Vision. FAL_KEY was never set in production, so that
tier returned None on every call for its entire lifetime — `category_hint` was
permanently None, no embedding was ever produced, and the B3.2b confusion-hint
path that keys off the hint was unreachable. It was removed rather than funded.
The `category_hint` plumbing is KEPT because it has a real supplier: the intake
API accepts a user-chosen category (`user_hints["category"]`), which is now
passed in here. See `openai_vision.build_system_prompt` for the allow-list guard
that a caller-supplied hint must pass.
"""

from __future__ import annotations

import logging

# Re-export public API so existing imports continue to work:
#   from app.ml.vision_classifier import classify_image
#   from app.ml.vision_classifier import ClassificationResult
#   from app.ml.vision_classifier import ALL_CATEGORIES, CATEGORY_DESCRIPTIONS
#   from app.ml.vision_classifier import OPENAI_API_KEY  (via config)
from app.config import OPENAI_API_KEY  # noqa: F401 — re-exported
from app.ml.vision_helpers import (  # noqa: F401 — re-exported
    ALL_CATEGORIES,
    CATEGORY_DESCRIPTIONS,
    CATEGORY_PROMPTS,
    CONDITION_KEYWORDS,
    ClassificationResult,
)
from app.ml.openai_vision import classify_openai_vision as _classify_openai_vision
from app.ml.confidence_aggregator import classify_heuristic as _classify_heuristic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def classify_image(
    image_bytes: bytes,
    filename: str = "",
    category_hint: str | None = None,
) -> ClassificationResult:
    """
    Classify and identify a collectible item image.

    Tier 1: OpenAI Vision — specific item identification
    Tier 2: Heuristic fallback (always available)

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, or WebP)
        filename: Original filename (used for heuristic hints — the heuristic
            tier matches on the FILENAME, so passing "" makes it near-useless)
        category_hint: Optional category the caller already knows (e.g. the
            category the user picked in the intake UI). Narrows the extraction
            prompt and enables the B3.2b confusion hint. Validated against
            ALL_CATEGORIES downstream; an unknown value is ignored, not trusted.

    Returns:
        ClassificationResult with category, confidence and condition
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

    # Tier 1: OpenAI Vision
    result = await _classify_openai_vision(image_bytes, filename, category_hint)
    if result is not None:
        return result

    # Tier 2: Heuristic (always returns a result)
    return _classify_heuristic(image_bytes, filename)
