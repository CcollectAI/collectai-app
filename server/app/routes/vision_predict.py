"""
Vision prediction & classification endpoint for CollectAI.

POST /vision-predict/classify  — classify an uploaded image of a collectible
GET  /vision-predict/health    — health check
GET  /vision-predict/categories — list supported categories with descriptions
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.config import VISION_MAX_IMAGE_BYTES as MAX_IMAGE_BYTES
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision-predict", tags=["vision-predict"])

# Per-user: 20 requests per minute for vision classification
_vision_user_limit = per_user_rate_limit(20, scope="vision")

# Allowed MIME types
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ClassificationResponse(BaseModel):
    category_id: str = Field(..., description="One of 36 canonical category IDs")
    category_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    condition: Optional[str] = Field(None, description="Detected condition, e.g. near_mint")
    condition_confidence: float = Field(0.0, ge=0.0, le=1.0)
    condition_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Numeric condition score 0.0-1.0")
    suggested_name: Optional[str] = Field(None, description="Suggested item name")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Extracted attributes")
    embedding_vector: Optional[list[float]] = Field(None, description="Image embedding vector if generated")
    classification_method: str = Field(..., description="clip, openai_vision, or heuristic")


class CategoryInfo(BaseModel):
    category_id: str
    description: str


class CategoriesResponse(BaseModel):
    categories: list[CategoryInfo]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    """Health check for the vision-predict service."""
    from app.ml.vision_classifier import FAL_KEY, OPENAI_API_KEY

    tier = "heuristic"
    if FAL_KEY:
        tier = "clip"
    elif OPENAI_API_KEY:
        tier = "openai_vision"

    return {
        "ok": True,
        "source": "vision-predict",
        "classification_tier": tier,
        "max_image_bytes": MAX_IMAGE_BYTES,
    }


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories():
    """List all 36 supported collectible categories with descriptions."""
    from app.ml.vision_classifier import ALL_CATEGORIES, CATEGORY_DESCRIPTIONS

    cats = [
        CategoryInfo(
            category_id=cat_id,
            description=CATEGORY_DESCRIPTIONS.get(cat_id, cat_id),
        )
        for cat_id in ALL_CATEGORIES
    ]
    return CategoriesResponse(categories=cats, total=len(cats))


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    dependencies=[Depends(get_current_user_id), Depends(_vision_user_limit)],
)
async def classify_image(file: UploadFile = File(..., description="Image of a collectible item")):
    """
    Classify an uploaded image of a collectible item.

    Uses a 3-tier classification approach:
    1. CLIP (fal.ai) for real image embeddings + zero-shot matching
    2. OpenAI Vision API for LLM-based classification
    3. Heuristic fallback using filename keywords and EXIF metadata

    Returns the predicted category, confidence, condition estimate, and optional embeddings.
    """
    # Validate content type
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise error_response(400, f"Unsupported image type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}")

    # Read and validate file size
    try:
        image_bytes = await file.read()
    except Exception:
        logger.warning("Failed to read uploaded file")
        raise error_response(400, "Failed to read uploaded file")

    if not image_bytes:
        raise error_response(400, "Empty file uploaded")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise error_response(413, f"Image too large. Maximum size: {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

    # Validate image magic bytes
    if not _is_valid_image(image_bytes):
        raise error_response(400, "File does not appear to be a valid image")

    # Sanitize filename
    raw_filename = os.path.basename(file.filename or "upload.jpg")
    safe_filename = re.sub(r"[^\w.\-]", "_", raw_filename)[:100]

    # Classify
    try:
        from app.ml.vision_classifier import classify_image as _classify

        result = await _classify(image_bytes, safe_filename)

        return ClassificationResponse(
            category_id=result.category_id,
            category_confidence=result.category_confidence,
            condition=result.condition,
            condition_confidence=result.condition_confidence,
            condition_score=_condition_to_score(result.condition),
            suggested_name=result.suggested_name,
            attributes=result.attributes,
            embedding_vector=result.embedding_vector,
            classification_method=result.classification_method,
        )
    except Exception as e:
        logger.error("Classification failed: %s", e, exc_info=True)
        raise error_response(500, "Classification failed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _condition_to_score(condition: Optional[str]) -> Optional[float]:
    """Convert categorical condition label to numeric 0.0-1.0 score."""
    if not condition:
        return None
    cond_lower = condition.lower().replace("_", " ")
    if "gem" in cond_lower or "pristine" in cond_lower:
        return 0.95
    if "near mint" in cond_lower or cond_lower == "nm":
        return 0.85
    if "mint" in cond_lower:
        return 0.95
    if "excellent" in cond_lower or cond_lower == "ex":
        return 0.75
    if "very good" in cond_lower or cond_lower == "vg":
        return 0.65
    if "good" in cond_lower or cond_lower == "lp":
        return 0.60
    if "fair" in cond_lower or "played" in cond_lower or cond_lower == "mp":
        return 0.45
    if "poor" in cond_lower or cond_lower == "hp" or "damaged" in cond_lower:
        return 0.25
    return 0.50


def _is_valid_image(data: bytes) -> bool:
    """Check magic bytes to verify the data is a valid image."""
    if len(data) < 4:
        return False
    # JPEG
    if data[:2] == b"\xff\xd8":
        return True
    # PNG
    if data[:4] == b"\x89PNG":
        return True
    # WebP
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    # GIF
    if data[:4] in (b"GIF8",):
        return True
    return False
