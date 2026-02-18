from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/screenshot-intel", tags=["screenshot-intel"])
logger = logging.getLogger(__name__)


class ScreenshotIntelRequest(BaseModel):
    screenshot_id: str = Field(..., description="Identifier of the uploaded screenshot")
    source_hint: Optional[str] = Field(
        None, description="ebay | vinted | instagram | reddit | other"
    )


class ScreenshotItemIntel(BaseModel):
    item_name: str
    estimated_value: float
    currency: str = "EUR"
    source_url: Optional[str] = None
    can_add_to_watchlist: bool = True
    listing_platform: Optional[str] = None


class ScreenshotIntelResponse(BaseModel):
    screenshot_id: str
    items: List[ScreenshotItemIntel]


@router.post("/analyze", response_model=ScreenshotIntelResponse)
async def analyze_screenshot(payload: ScreenshotIntelRequest) -> ScreenshotIntelResponse:
    """
    Screenshot extraction endpoint (proof-of-concept).

    Real implementation requires multimodal OCR + marketplace scraping which
    is not yet wired up.  Returns a 501 status with an empty items list so
    the frontend can distinguish between 'no results found' (200) and
    'feature not implemented yet' (501).
    """
    logger.info(
        f"[screenshot-intel/analyze] Received request for screenshot_id={payload.screenshot_id}, "
        f"source_hint={payload.source_hint} -- OCR pipeline not yet implemented"
    )

    # Return 501 Not Implemented with an honest empty result
    return JSONResponse(
        status_code=501,
        content={
            "screenshot_id": payload.screenshot_id,
            "items": [],
            "detail": (
                "Screenshot analysis is not yet implemented. "
                "Multimodal OCR and marketplace scraping are planned for a future release."
            ),
        },
    )
