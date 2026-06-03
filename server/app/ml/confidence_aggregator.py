"""
Confidence score aggregation and heuristic fallback classification.

Contains the heuristic classifier (Tier 3) which uses filename keywords,
EXIF metadata, and barcode detection as a last-resort fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.ml.vision_helpers import (
    ClassificationResult,
    HEURISTIC_PATTERNS,
    detect_condition_from_text,
)

logger = logging.getLogger(__name__)


def classify_heuristic(image_bytes: bytes, filename: str) -> ClassificationResult:
    """
    Heuristic fallback classification using filename keywords and image metadata.
    Always returns a result (never None).
    """
    logger.info("vision_classifier: using heuristic fallback")

    text_to_match = filename.lower() if filename else ""

    # S5: detect EXIF *presence* only — do NOT decode raw EXIF bytes into the
    # text we category-match on. The old code scanned 2KB of arbitrary bytes
    # after the "Exif" marker and fed the decoded ASCII into the pattern
    # matcher, which was both unreliable (camera make/model spuriously matches
    # patterns) and an injection vector (a crafted EXIF blob could nudge the
    # category). The presence flag is harmless; the raw-text scan is gone.
    has_exif = False
    try:
        if image_bytes[:2] == b"\xff\xd8" and image_bytes.find(b"Exif") > 0:
            has_exif = True
    except Exception:
        pass

    combined_text = text_to_match

    # Match against heuristic patterns
    best_cat: str | None = None
    best_score = 0.0

    for cat_id, patterns in HEURISTIC_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                # Score based on pattern specificity (longer patterns = more specific)
                score = 0.5 + min(len(pattern) / 50.0, 0.3)
                if score > best_score:
                    best_score = score
                    best_cat = cat_id

    # Check for barcode-like patterns in filename
    barcode_match = re.search(r"\b(\d{10,13})\b", text_to_match)
    barcode_info: dict[str, Any] = {}
    if barcode_match:
        barcode_info["barcode"] = barcode_match.group(1)
        # ISBN-13 prefix 978/979 suggests a book/manga
        if barcode_match.group(1).startswith(("978", "979")):
            if best_cat is None:
                best_cat = "manga"
                best_score = 0.55
            barcode_info["barcode_type"] = "isbn13"
        else:
            barcode_info["barcode_type"] = "ean13"

    # Detect condition
    condition, cond_conf = detect_condition_from_text(combined_text)

    # If nothing matched at all, signal failure with explicit low confidence
    if best_cat is None:
        best_cat = "unknown"
        best_score = 0.0

    attributes: dict[str, Any] = {}
    if barcode_info:
        attributes["barcode"] = barcode_info
    if has_exif:
        attributes["has_exif"] = True

    logger.info(
        "Heuristic classification: category=%s confidence=%.4f source=filename",
        best_cat, best_score,
    )

    return ClassificationResult(
        category_id=best_cat,
        category_confidence=best_score,
        condition=condition,
        condition_confidence=cond_conf,
        suggested_name=None,
        attributes=attributes,
        embedding_vector=None,
        classification_method="heuristic",
        model_version="heuristic:v1",
    )
