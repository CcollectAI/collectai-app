from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/quickscan-advanced", tags=["quickscan-advanced"])
logger = logging.getLogger(__name__)


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
    explanation: str | None = Field(
        None, description="Human-readable explanation of the price estimate"
    )


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


# Demo fallback data
DEMO_ATTRS = QuickScanAttributes(
    category="mtg",
    edition_guess="Unlimited",
    condition_guess="Near Mint",
    rarity_score=0.82,
)

DEMO_PREDICTION = QuickScanPrediction(
    name="Demo Black Lotus",
    estimated_low=18000.0,
    estimated_mid=22000.0,
    estimated_high=26000.0,
    currency="EUR",
    confidence=0.91,
    explanation="Priced based on excellent condition, rarity, and strong market demand.",
)


async def _get_real_prediction(
    category: str,
    attrs: QuickScanAttributes,
) -> QuickScanPrediction | None:
    """
    Attempt to get a real model prediction for the category.
    Returns None if no model is available.
    """
    try:
        from app.ml.model_loader import get_active_model
        from app.ml.explainer import generate_explanation, generate_simple_explanation
        from inference import ridge_infer_quantiles

        # Load model for category
        artifact = await get_active_model(category)
        if artifact is None:
            logger.info(f"No model available for category: {category}")
            return None

        # Build features from attributes
        # This is a simplified feature set - real implementation would extract more
        features = {
            "condition_score": _condition_to_score(attrs.condition_guess),
            "rarity_score": attrs.rarity_score or 0.5,
            "edition_score": _edition_to_score(attrs.edition_guess),
        }

        # Get quantile predictions
        quantiles = ridge_infer_quantiles(artifact, features)
        if quantiles is None:
            logger.warning(f"Model inference failed for {category}")
            return None

        # Generate explanation
        explanation = generate_explanation(features, artifact)
        if not explanation or explanation == "Price estimate based on market data and item characteristics.":
            # Fallback to simple explanation
            explanation = generate_simple_explanation(
                category,
                attrs.condition_guess,
                attrs.edition_guess,
                attrs.rarity_score,
            )

        return QuickScanPrediction(
            name=f"Detected {category.upper()} item",
            estimated_low=quantiles["q10"],
            estimated_mid=quantiles["q50"],
            estimated_high=quantiles["q90"],
            currency="EUR",
            confidence=0.75,  # Default confidence for real model
            explanation=explanation,
        )

    except ImportError as e:
        logger.warning(f"Import error in real prediction: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error getting real prediction: {e}")
        return None


def _condition_to_score(condition: str | None) -> float:
    """Convert condition string to 0-1 score."""
    if not condition:
        return 0.5

    cond_lower = condition.lower()
    if "mint" in cond_lower or "gem" in cond_lower:
        return 0.95
    elif "near mint" in cond_lower or "nm" in cond_lower:
        return 0.85
    elif "excellent" in cond_lower or "ex" in cond_lower:
        return 0.75
    elif "good" in cond_lower or "lp" in cond_lower:
        return 0.60
    elif "played" in cond_lower or "mp" in cond_lower:
        return 0.45
    elif "poor" in cond_lower or "hp" in cond_lower or "damaged" in cond_lower:
        return 0.25
    return 0.5


def _edition_to_score(edition: str | None) -> float:
    """Convert edition string to 0-1 score."""
    if not edition:
        return 0.5

    ed_lower = edition.lower()
    if "1st" in ed_lower or "first" in ed_lower or "alpha" in ed_lower or "beta" in ed_lower:
        return 0.95
    elif "shadowless" in ed_lower:
        return 0.90
    elif "unlimited" in ed_lower:
        return 0.70
    elif "promo" in ed_lower:
        return 0.65
    elif "reprint" in ed_lower:
        return 0.40
    return 0.5


@router.post("/single", response_model=QuickScanResult)
async def quickscan_single_demo():
    """
    Enriched QuickScan: edition, condition, rarity, q10/q50/q90 band.

    Attempts to use real model if available, falls back to demo data.
    """
    # Try real model first
    real_pred = await _get_real_prediction(DEMO_ATTRS.category, DEMO_ATTRS)

    if real_pred:
        return QuickScanResult(
            item_id=None,
            attributes=DEMO_ATTRS,
            prediction=real_pred,
        )

    # Fallback to demo
    return QuickScanResult(
        item_id=None,
        attributes=DEMO_ATTRS,
        prediction=DEMO_PREDICTION,
    )


@router.post("/batch", response_model=BatchQuickScanResponse)
async def quickscan_batch_demo(payload: BatchQuickScanRequest):
    """
    Multi-item batch scanning (Advanced D).
    Attempts real model, falls back to demo per image.
    """
    results: list[QuickScanResult] = []

    for image_id in payload.image_ids:
        # For batch, we'd normally extract category from image
        # For now, use funko as demo category for batch
        attrs = QuickScanAttributes(
            category="funko",
            edition_guess="Convention Exclusive",
            condition_guess="Boxed",
            rarity_score=0.7,
        )

        # Try real model
        real_pred = await _get_real_prediction(attrs.category, attrs)

        if real_pred:
            real_pred.name = f"Detected item from {image_id}"
            results.append(
                QuickScanResult(
                    item_id=None,
                    attributes=attrs,
                    prediction=real_pred,
                )
            )
        else:
            # Fallback to demo
            pred = QuickScanPrediction(
                name=f"Demo Funko from {image_id}",
                estimated_low=35.0,
                estimated_mid=45.0,
                estimated_high=60.0,
                currency="EUR",
                confidence=0.8,
                explanation="Estimate based on recent Funko Pop market sales.",
            )
            results.append(
                QuickScanResult(
                    item_id=None,
                    attributes=attrs,
                    prediction=pred,
                )
            )

    return BatchQuickScanResponse(results=results)
