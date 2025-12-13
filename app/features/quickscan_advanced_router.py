from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/quickscan-advanced", tags=["quickscan-advanced"])


class QuickScanAttributes(BaseModel):
    category: str
    edition_guess: str | None = None
    condition_guess: str | None = None
    rarity_score: float | None = Field(
        None, description="0-1 rarity estimate based on visual cues"
    )


class QuickScanPrediction(BaseModel):
    name: str
    estimated_low: float
    estimated_mid: float
    estimated_high: float
    currency: str = "EUR"
    confidence: float = Field(..., description="0-1 model confidence")


class QuickScanResult(BaseModel):
    item_id: str | None = None
    attributes: QuickScanAttributes
    prediction: QuickScanPrediction


class BatchQuickScanRequest(BaseModel):
    image_ids: List[str] = Field(
        ..., description="Identifiers of uploaded images (S3 keys, etc.)"
    )


class BatchQuickScanResponse(BaseModel):
    results: List[QuickScanResult]


@router.post("/single", response_model=QuickScanResult)
async def quickscan_single_demo():
    """
    Enriched QuickScan: edition, condition, rarity, q10/q50/q90 band.

    Later this will call your real multimodal model; for now,
    it's a deterministic demo object so the Add flow can be wired.
    """
    attrs = QuickScanAttributes(
        category="mtg",
        edition_guess="Unlimited",
        condition_guess="Near Mint",
        rarity_score=0.82,
    )
    pred = QuickScanPrediction(
        name="Demo Black Lotus",
        estimated_low=18000.0,
        estimated_mid=22000.0,
        estimated_high=26000.0,
        currency="EUR",
        confidence=0.91,
    )
    return QuickScanResult(
        item_id=None,
        attributes=attrs,
        prediction=pred,
    )


@router.post("/batch", response_model=BatchQuickScanResponse)
async def quickscan_batch_demo(payload: BatchQuickScanRequest):
    """
    Multi-item batch scanning (Advanced D).
    For now returns 1 demo item per image.
    """
    results: list[QuickScanResult] = []
    for image_id in payload.image_ids:
        attrs = QuickScanAttributes(
            category="funko",
            edition_guess="Convention Exclusive",
            condition_guess="Boxed",
            rarity_score=0.7,
        )
        pred = QuickScanPrediction(
            name=f"Demo Funko from {image_id}",
            estimated_low=35.0,
            estimated_mid=45.0,
            estimated_high=60.0,
            currency="EUR",
            confidence=0.8,
        )
        results.append(
            QuickScanResult(
                item_id=None,
                attributes=attrs,
                prediction=pred,
            )
        )
    return BatchQuickScanResponse(results=results)
