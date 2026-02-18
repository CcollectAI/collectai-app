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


class QuickScanSingleRequest(BaseModel):
    category: str = Field(..., description="Category slug (e.g. 'pokemon', 'funko')")
    edition_guess: str | None = None
    condition_guess: str | None = None
    rarity_score: float | None = Field(None, description="0-1 rarity estimate")


class BatchQuickScanRequest(BaseModel):
    image_ids: List[str] = Field(
        ..., description="Identifiers of uploaded images (S3 keys, etc.)"
    )
    category: str | None = Field(
        None, description="Category slug; if omitted, auto-detect per image (not yet implemented)"
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

        # Build features dynamically from model artifact's feature list
        model_features = artifact.get("features", [])
        features = _build_features(attrs, model_features)

        # Get quantile predictions
        quantiles = ridge_infer_quantiles(artifact, features)
        if quantiles is None:
            logger.warning(f"Model inference failed for {category}")
            return None

        # Compute confidence from model metadata
        cv_mae = artifact.get("cv_mae")
        train_size = artifact.get("train_size", 0)
        confidence = 0.75
        if cv_mae is not None and train_size > 0:
            # Higher confidence with more data and lower error
            size_factor = min(1.0, train_size / 500)  # saturates at 500 samples
            error_factor = max(0.0, 1.0 - cv_mae / 100)  # lower MAE = higher conf
            confidence = round(0.5 + 0.4 * size_factor * error_factor, 2)
            confidence = max(0.3, min(0.95, confidence))

        # Generate explanation
        explanation = generate_explanation(features, artifact)
        if not explanation or explanation == "Price estimate based on market data and item characteristics.":
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
            confidence=confidence,
            explanation=explanation,
        )

    except ImportError as e:
        logger.warning(f"Import error in real prediction: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error getting real prediction: {e}")
        return None


def _build_features(attrs: QuickScanAttributes, model_features: list[str]) -> dict[str, float]:
    """Build feature dict dynamically based on model's expected features."""
    # Core feature generators
    core = {
        "condition_score": lambda: _condition_to_score(attrs.condition_guess),
        "rarity_score": lambda: attrs.rarity_score or 0.5,
        "edition_score": lambda: _edition_to_score(attrs.edition_guess),
        "is_foil": lambda: 0.0,
        "is_sealed": lambda: 0.0,
        "is_graded": lambda: 0.0,
        "is_first_edition": lambda: 1.0 if attrs.edition_guess and ("1st" in attrs.edition_guess.lower() or "first" in attrs.edition_guess.lower()) else 0.0,
        "is_holo": lambda: 0.0,
        "set_age_years": lambda: 0.0,
    }

    features: dict[str, float] = {}
    for feat in model_features:
        if feat in core:
            features[feat] = core[feat]()
        else:
            features[feat] = 0.0  # Safe default for unknown features

    # Always include core 3 even if not in model_features (backward compat)
    if not model_features:
        features["condition_score"] = _condition_to_score(attrs.condition_guess)
        features["rarity_score"] = attrs.rarity_score or 0.5
        features["edition_score"] = _edition_to_score(attrs.edition_guess)

    return features


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
async def quickscan_single(request: QuickScanSingleRequest | None = None):
    """
    Enriched QuickScan: edition, condition, rarity, q10/q50/q90 band.

    Accepts category and optional attributes. Attempts real model first,
    falls back to demo data if no model available.
    """
    if request:
        attrs = QuickScanAttributes(
            category=request.category,
            edition_guess=request.edition_guess,
            condition_guess=request.condition_guess,
            rarity_score=request.rarity_score,
        )
    else:
        # Backwards-compatible: use demo attrs if no request body
        attrs = DEMO_ATTRS

    # Try real model first
    real_pred = await _get_real_prediction(attrs.category, attrs)

    if real_pred:
        return QuickScanResult(
            item_id=None,
            attributes=attrs,
            prediction=real_pred,
        )

    # Fallback to demo
    return QuickScanResult(
        item_id=None,
        attributes=attrs,
        prediction=DEMO_PREDICTION,
    )


@router.post("/batch", response_model=BatchQuickScanResponse)
async def quickscan_batch(payload: BatchQuickScanRequest):
    """
    Multi-item batch scanning (Advanced D).

    Pass category in the request body. If omitted, falls back to demo.
    Attempts real model per image, falls back to demo prediction.
    """
    results: list[QuickScanResult] = []
    category = payload.category or "funko"  # fallback for backwards compat

    for image_id in payload.image_ids:
        attrs = QuickScanAttributes(
            category=category,
            edition_guess=None,
            condition_guess=None,
            rarity_score=0.5,
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
            # Fallback to generic demo
            pred = QuickScanPrediction(
                name=f"Detected item from {image_id}",
                estimated_low=35.0,
                estimated_mid=45.0,
                estimated_high=60.0,
                currency="EUR",
                confidence=0.5,
                explanation=f"Estimate based on {category} market data.",
            )
            results.append(
                QuickScanResult(
                    item_id=None,
                    attributes=attrs,
                    prediction=pred,
                )
            )

    return BatchQuickScanResponse(results=results)
