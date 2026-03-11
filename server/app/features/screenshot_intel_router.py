"""
Screenshot Intel Router — Extract collectible info from screenshots.

Accepts a screenshot (by ID from the quickscan upload flow), runs it through
the existing vision classification pipeline, and returns structured item data
with estimated values. Useful for analyzing marketplace screenshots, social
media posts, or any image containing collectible items.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.errors import error_response
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/screenshot-intel", tags=["Screenshot Intel"])
logger = logging.getLogger(__name__)

_screenshot_limit = per_user_rate_limit(10, window_seconds=60, scope="screenshot_intel")


class ScreenshotIntelRequest(BaseModel):
    screenshot_id: str = Field(..., description="Identifier of the uploaded screenshot (from /quickscan/upload-image)")
    source_hint: Optional[str] = Field(
        None, description="ebay | vinted | instagram | reddit | other"
    )
    category_hint: Optional[str] = Field(
        None, description="Category hint to improve classification accuracy"
    )


class ScreenshotItemIntel(BaseModel):
    item_name: str
    category: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: str = "EUR"
    confidence: float = 0.0
    condition_guess: Optional[str] = None
    source_url: Optional[str] = None
    can_add_to_watchlist: bool = True
    listing_platform: Optional[str] = None


class ScreenshotIntelResponse(BaseModel):
    screenshot_id: str
    items: List[ScreenshotItemIntel]
    identification_method: str = "vision_openai"


@router.post("/analyze", response_model=ScreenshotIntelResponse)
async def analyze_screenshot(
    payload: ScreenshotIntelRequest,
    _rl=Depends(_screenshot_limit),
) -> ScreenshotIntelResponse:
    """
    Analyze a screenshot to extract collectible item information.

    Uses the existing vision classification pipeline (OpenAI Vision) to
    identify items in the screenshot and estimate their values.

    The screenshot_id should come from the /quickscan/upload-image endpoint.
    """
    # Locate the screenshot file
    tmp_dir = Path(os.getenv("QUICKSCAN_TMP_DIR", "/tmp"))
    matching = list(tmp_dir.glob(f"{payload.screenshot_id}_*"))

    if not matching:
        raise error_response(404, "Screenshot not found. Upload via /quickscan/upload-image first.")

    image_path = matching[0]
    image_bytes = image_path.read_bytes()

    if len(image_bytes) < 100:
        raise error_response(400, "Screenshot file is too small or corrupt.")

    # Run through the intake pipeline (vision classification)
    try:
        from app.agents.intake_agent import process_intake

        result = await process_intake(
            image_bytes=image_bytes,
            user_hints={
                "category": payload.category_hint,
                "source": payload.source_hint,
            } if (payload.category_hint or payload.source_hint) else None,
        )

        items = []
        if result.name:
            items.append(ScreenshotItemIntel(
                item_name=result.name,
                category=result.category_id,
                estimated_value=result.estimated_price,
                currency="EUR",
                confidence=result.category_confidence or 0.0,
                condition_guess=result.attributes.get("condition_guess") if result.attributes else None,
                listing_platform=payload.source_hint,
            ))

        return ScreenshotIntelResponse(
            screenshot_id=payload.screenshot_id,
            items=items,
            identification_method=result.identification_method or "vision_openai",
        )

    except Exception as e:
        logger.error("[screenshot-intel] Vision pipeline error: %s", e)
        raise error_response(500, "Failed to analyze screenshot")
