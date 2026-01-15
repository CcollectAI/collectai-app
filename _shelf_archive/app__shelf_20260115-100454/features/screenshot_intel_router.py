from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/screenshot-intel", tags=["screenshot-intel"])


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
    Proof-of-concept screenshot extraction.

    Later this will use multimodal OCR + scraping.
    For now, returns one deterministic item per screenshot.
    """
    platform = payload.source_hint or "ebay"
    item = ScreenshotItemIntel(
        item_name="Demo Grail from screenshot",
        estimated_value=120.0,
        currency="EUR",
        source_url="https://example.com/demo-listing",
        can_add_to_watchlist=True,
        listing_platform=platform,
    )
    return ScreenshotIntelResponse(
        screenshot_id=payload.screenshot_id,
        items=[item],
    )
