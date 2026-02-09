from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _standardize(features: dict, cols: list, mu: list, sd: list) -> list[float]:
    """Standardize features using model's stored mean/std."""
    return [
        (float(features.get(c, 0.0)) - float(mu[i])) / (float(sd[i]) or 1.0)
        for i, c in enumerate(cols)
    ]


def _linear_predict(x: list[float], coef: list, intercept: float) -> float:
    """Compute linear prediction from standardized features."""
    return float(intercept + sum(ci * xi for ci, xi in zip(coef, x)))


def ridge_infer(artifact: dict, features: dict) -> float | None:
    """Return q50 prediction or None if artifact is not a supported ridge model."""
    model_type = artifact.get("model_type", "")
    if model_type not in ("ridge_v1", "ridge_v2"):
        return None
    cols = artifact.get("features", [])
    mu = artifact.get("standardizer", {}).get("mean", [])
    sd = artifact.get("standardizer", {}).get("std", [])
    coef = artifact.get("ridge", {}).get("coef", [])
    intercept = artifact.get("ridge", {}).get("intercept", 0.0)

    if not cols or len(cols) != len(coef):
        if cols and coef:
            logger.warning(
                "ridge_infer: coef length mismatch for %s — features=%d, coef=%d",
                artifact.get("category", "unknown"), len(cols), len(coef),
            )
        return None

    x = _standardize(features, cols, mu, sd)
    return _linear_predict(x, coef, intercept)


def ridge_infer_quantiles(artifact: dict, features: dict) -> dict[str, float] | None:
    """
    Return quantile predictions (q10, q50, q90) or None if unsupported model.

    - ridge_v2: Uses trained QuantileRegressor coefficients for q10/q90
    - ridge_v1: Falls back to uncertainty_scale spread around q50
    """
    q50 = ridge_infer(artifact, features)
    if q50 is None:
        return None

    model_type = artifact.get("model_type", "")
    cols = artifact.get("features", [])
    mu = artifact.get("standardizer", {}).get("mean", [])
    sd = artifact.get("standardizer", {}).get("std", [])

    q10 = None
    q90 = None

    # ridge_v2: use trained quantile coefficients if available
    if model_type == "ridge_v2":
        q10_data = artifact.get("ridge_q10")
        q90_data = artifact.get("ridge_q90")

        if q10_data and q90_data:
            x = _standardize(features, cols, mu, sd)
            q10_coef = q10_data.get("coef", [])
            q10_intercept = q10_data.get("intercept", 0.0)
            q90_coef = q90_data.get("coef", [])
            q90_intercept = q90_data.get("intercept", 0.0)

            if len(q10_coef) == len(cols) and len(q90_coef) == len(cols):
                q10 = _linear_predict(x, q10_coef, q10_intercept)
                q90 = _linear_predict(x, q90_coef, q90_intercept)
            else:
                logger.warning(
                    "ridge_infer_quantiles: q10/q90 coef mismatch for %s — features=%d, q10_coef=%d, q90_coef=%d",
                    artifact.get("category", "unknown"), len(cols), len(q10_coef), len(q90_coef),
                )

    # Fallback: uncertainty_scale spread (ridge_v1 or missing q10/q90 data)
    if q10 is None or q90 is None:
        uncertainty_scale = artifact.get("uncertainty_scale", 0.15)
        if not isinstance(uncertainty_scale, (int, float)):
            uncertainty_scale = 0.15
        uncertainty_scale = max(0.05, min(0.50, float(uncertainty_scale)))
        q10 = q50 * (1.0 - uncertainty_scale)
        q90 = q50 * (1.0 + uncertainty_scale)

    # Ensure non-negative and proper ordering
    q10 = max(0.0, q10)
    q90 = max(q10, q90)
    q50 = max(q10, min(q90, q50))  # Clamp q50 within bounds

    return {
        "q10": round(q10, 2),
        "q50": round(q50, 2),
        "q90": round(q90, 2),
    }
