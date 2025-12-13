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
