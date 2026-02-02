from __future__ import annotations


def ridge_infer(artifact: dict, features: dict) -> float | None:
    """Return prediction or None if artifact is not ridge_v1."""
    if artifact.get("model_type") != "ridge_v1":
        return None
    cols = artifact["features"]
    mu = artifact["standardizer"]["mean"]
    sd = artifact["standardizer"]["std"]
    coef = artifact["ridge"]["coef"]
    intercept = artifact["ridge"]["intercept"]
    x = [
        (float(features.get(c, 0.0)) - float(mu[i])) / (float(sd[i]) or 1.0)
        for i, c in enumerate(cols)
    ]
    return float(intercept + sum(ci * xi for ci, xi in zip(coef, x)))


def ridge_infer_quantiles(artifact: dict, features: dict) -> dict[str, float] | None:
    """
    Return quantile predictions (q10, q50, q90) or None if artifact is not ridge_v1.

    Uses the model's uncertainty_scale if available, otherwise defaults to 15%.
    The spread is calculated as: q10 = q50 * (1 - scale), q90 = q50 * (1 + scale)
    """
    q50 = ridge_infer(artifact, features)
    if q50 is None:
        return None

    # Get uncertainty scale from artifact or use 15% default
    uncertainty_scale = artifact.get("uncertainty_scale", 0.15)
    if not isinstance(uncertainty_scale, (int, float)):
        uncertainty_scale = 0.15
    uncertainty_scale = max(0.05, min(0.50, float(uncertainty_scale)))  # Clamp to 5-50%

    # Calculate quantiles
    q10 = q50 * (1.0 - uncertainty_scale)
    q90 = q50 * (1.0 + uncertainty_scale)

    # Ensure non-negative
    q10 = max(0.0, q10)
    q90 = max(q10, q90)

    return {
        "q10": round(q10, 2),
        "q50": round(q50, 2),
        "q90": round(q90, 2),
    }
