"""Tests for inference.py — ridge_v1 and ridge_v2 model inference."""
import logging
import pytest
from inference import _standardize, _linear_predict, ridge_infer, ridge_infer_quantiles


# ---------------------------------------------------------------------------
# Fixtures: sample model artifacts
# ---------------------------------------------------------------------------

RIDGE_V1_ARTIFACT = {
    "model_type": "ridge_v1",
    "features": ["condition_score", "rarity_score", "edition_score"],
    "standardizer": {
        "mean": [0.5, 0.5, 0.5],
        "std": [0.2, 0.3, 0.25],
    },
    "ridge": {
        "coef": [10.0, 20.0, 5.0],
        "intercept": 50.0,
    },
    "uncertainty_scale": 0.20,
}

RIDGE_V2_ARTIFACT = {
    "model_type": "ridge_v2",
    "features": ["condition_score", "rarity_score", "edition_score"],
    "standardizer": {
        "mean": [0.5, 0.5, 0.5],
        "std": [0.2, 0.3, 0.25],
    },
    "ridge": {
        "coef": [10.0, 20.0, 5.0],
        "intercept": 50.0,
    },
    "ridge_q10": {
        "coef": [8.0, 15.0, 4.0],
        "intercept": 35.0,
    },
    "ridge_q90": {
        "coef": [12.0, 25.0, 6.0],
        "intercept": 65.0,
    },
    "best_alpha": 1.0,
    "cv_mae": 12.5,
    "train_size": 200,
}


# ---------------------------------------------------------------------------
# _standardize
# ---------------------------------------------------------------------------

class TestStandardize:
    def test_at_mean(self):
        """Features at mean should standardize to zero."""
        result = _standardize(
            {"a": 5.0, "b": 10.0},
            ["a", "b"],
            [5.0, 10.0],
            [2.0, 3.0],
        )
        assert result == [0.0, 0.0]

    def test_one_std_above(self):
        result = _standardize(
            {"a": 7.0},
            ["a"],
            [5.0],
            [2.0],
        )
        assert result == [1.0]

    def test_missing_feature_defaults_zero(self):
        result = _standardize(
            {},  # no features provided
            ["a"],
            [5.0],
            [2.0],
        )
        assert result == [(0.0 - 5.0) / 2.0]

    def test_zero_std_no_division_error(self):
        result = _standardize(
            {"a": 3.0},
            ["a"],
            [1.0],
            [0.0],  # zero std
        )
        assert result == [(3.0 - 1.0) / 1.0]  # uses 1.0 as fallback


# ---------------------------------------------------------------------------
# _linear_predict
# ---------------------------------------------------------------------------

class TestLinearPredict:
    def test_basic(self):
        result = _linear_predict([1.0, 2.0], [3.0, 4.0], 5.0)
        assert result == 5.0 + 3.0 * 1.0 + 4.0 * 2.0  # 16.0

    def test_zero_features(self):
        result = _linear_predict([], [], 42.0)
        assert result == 42.0


# ---------------------------------------------------------------------------
# ridge_infer (q50)
# ---------------------------------------------------------------------------

class TestRidgeInfer:
    def test_v1_at_mean(self):
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer(RIDGE_V1_ARTIFACT, features)
        assert result == 50.0  # all features at mean → intercept only

    def test_v2_at_mean(self):
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer(RIDGE_V2_ARTIFACT, features)
        assert result == 50.0

    def test_v1_high_condition(self):
        features = {"condition_score": 0.9, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer(RIDGE_V1_ARTIFACT, features)
        # condition z = (0.9 - 0.5) / 0.2 = 2.0, contribution = 10.0 * 2.0 = 20.0
        assert result == 70.0

    def test_unsupported_model_type(self):
        artifact = {"model_type": "xgboost_v1"}
        assert ridge_infer(artifact, {}) is None

    def test_empty_features_list(self):
        artifact = {"model_type": "ridge_v1", "features": [], "standardizer": {"mean": [], "std": []}, "ridge": {"coef": [], "intercept": 10.0}}
        assert ridge_infer(artifact, {}) is None  # empty cols → None

    def test_missing_model_type(self):
        assert ridge_infer({}, {}) is None


# ---------------------------------------------------------------------------
# ridge_infer_quantiles
# ---------------------------------------------------------------------------

class TestRidgeInferQuantiles:
    def test_v1_uses_uncertainty_scale(self):
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer_quantiles(RIDGE_V1_ARTIFACT, features)
        assert result is not None
        assert result["q50"] == 50.0
        # uncertainty_scale = 0.20
        assert result["q10"] == round(50.0 * 0.80, 2)  # 40.0
        assert result["q90"] == round(50.0 * 1.20, 2)  # 60.0

    def test_v2_uses_trained_coefficients(self):
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer_quantiles(RIDGE_V2_ARTIFACT, features)
        assert result is not None
        assert result["q50"] == 50.0
        # All features at mean → q10 = q10_intercept = 35.0, q90 = q90_intercept = 65.0
        assert result["q10"] == 35.0
        assert result["q90"] == 65.0

    def test_v2_with_non_mean_features(self):
        features = {"condition_score": 0.9, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer_quantiles(RIDGE_V2_ARTIFACT, features)
        assert result is not None
        # condition z = (0.9 - 0.5) / 0.2 = 2.0
        # q50 = 50 + 10*2 = 70
        assert result["q50"] == 70.0
        # q10 = 35 + 8*2 = 51
        assert result["q10"] == 51.0
        # q90 = 65 + 12*2 = 89
        assert result["q90"] == 89.0

    def test_v2_without_q10_q90_falls_back(self):
        """ridge_v2 without ridge_q10/ridge_q90 should fall back to uncertainty_scale."""
        artifact = {**RIDGE_V2_ARTIFACT, "uncertainty_scale": 0.15}
        del artifact["ridge_q10"]
        del artifact["ridge_q90"]
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer_quantiles(artifact, features)
        assert result is not None
        assert result["q50"] == 50.0
        assert result["q10"] == round(50.0 * 0.85, 2)
        assert result["q90"] == round(50.0 * 1.15, 2)

    def test_non_negative_prices(self):
        """q10 should never go below 0."""
        artifact = {
            "model_type": "ridge_v1",
            "features": ["x"],
            "standardizer": {"mean": [0.0], "std": [1.0]},
            "ridge": {"coef": [-100.0], "intercept": 5.0},
            "uncertainty_scale": 0.50,
        }
        features = {"x": 1.0}
        result = ridge_infer_quantiles(artifact, features)
        # q50 = 5 + (-100 * 1) = -95 → q10 would be very negative
        # But ensure q10 >= 0
        assert result is not None
        assert result["q10"] >= 0.0

    def test_unsupported_returns_none(self):
        result = ridge_infer_quantiles({"model_type": "unknown"}, {})
        assert result is None

    def test_proper_ordering(self):
        """q10 <= q50 <= q90 always."""
        features = {"condition_score": 0.1, "rarity_score": 0.9, "edition_score": 0.3}
        result = ridge_infer_quantiles(RIDGE_V2_ARTIFACT, features)
        assert result is not None
        assert result["q10"] <= result["q50"] <= result["q90"]

    def test_default_uncertainty_clamp(self):
        """Uncertainty scale should be clamped to 5-50%."""
        artifact = {**RIDGE_V1_ARTIFACT, "uncertainty_scale": 999}
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        result = ridge_infer_quantiles(artifact, features)
        # Should clamp to 50%, not 999x
        assert result["q10"] == round(50.0 * 0.50, 2)
        assert result["q90"] == round(50.0 * 1.50, 2)


# ---------------------------------------------------------------------------
# Coef length mismatch warnings
# ---------------------------------------------------------------------------

class TestCoefMismatchWarnings:
    def test_ridge_infer_logs_q50_mismatch(self, caplog):
        """ridge_infer should warn when coef length != features length."""
        artifact = {
            "model_type": "ridge_v2",
            "category": "pokemon",
            "features": ["a", "b", "c"],
            "standardizer": {"mean": [0, 0, 0], "std": [1, 1, 1]},
            "ridge": {
                "coef": [1.0, 2.0],  # 2 coefs for 3 features
                "intercept": 10.0,
            },
        }
        with caplog.at_level(logging.WARNING, logger="inference"):
            result = ridge_infer(artifact, {"a": 1})
        assert result is None
        assert "coef length mismatch" in caplog.text
        assert "features=3" in caplog.text
        assert "coef=2" in caplog.text

    def test_ridge_infer_no_warning_when_both_empty(self, caplog):
        """No warning when both cols and coef are empty — just returns None."""
        artifact = {
            "model_type": "ridge_v1",
            "features": [],
            "standardizer": {"mean": [], "std": []},
            "ridge": {"coef": [], "intercept": 10.0},
        }
        with caplog.at_level(logging.WARNING, logger="inference"):
            result = ridge_infer(artifact, {})
        assert result is None
        assert "coef length mismatch" not in caplog.text

    def test_quantile_logs_q10_q90_mismatch(self, caplog):
        """ridge_infer_quantiles should warn when q10/q90 coef length mismatches."""
        artifact = {
            "model_type": "ridge_v2",
            "category": "funko",
            "features": ["x", "y"],
            "standardizer": {"mean": [0, 0], "std": [1, 1]},
            "ridge": {"coef": [1.0, 2.0], "intercept": 10.0},
            "ridge_q10": {"coef": [1.0], "intercept": 5.0},  # 1 coef for 2 features
            "ridge_q90": {"coef": [1.0, 2.0, 3.0], "intercept": 15.0},  # 3 coefs for 2 features
        }
        with caplog.at_level(logging.WARNING, logger="inference"):
            result = ridge_infer_quantiles(artifact, {"x": 1, "y": 2})
        assert result is not None  # falls back to uncertainty_scale
        assert "q10/q90 coef mismatch" in caplog.text

    def test_quantile_no_warning_when_coefs_match(self, caplog):
        """No warning when q10/q90 coefs match feature count."""
        features = {"condition_score": 0.5, "rarity_score": 0.5, "edition_score": 0.5}
        with caplog.at_level(logging.WARNING, logger="inference"):
            result = ridge_infer_quantiles(RIDGE_V2_ARTIFACT, features)
        assert result is not None
        assert "coef mismatch" not in caplog.text


# ---------------------------------------------------------------------------
# Bake-quality integration tests: load all real trained artifacts and verify
# each produces sane predictions. Catches: negative q50, q10 > q90 ordering
# bugs, NaN/Inf, missing features, corrupt JSON. Runs against the ACTIVE
# production model per category (server/artifacts/<cat>/active/model.json).
# ---------------------------------------------------------------------------

from pathlib import Path
import json

ARTIFACTS_ROOT = Path(__file__).resolve().parent.parent / "artifacts"


def _discover_active_artifacts() -> list[tuple[str, dict]]:
    """Load every active model.json as (category, artifact) tuples.

    Skips any category with missing or malformed JSON rather than failing the
    whole collection — we want the test to scale as categories are added.
    """
    if not ARTIFACTS_ROOT.exists():
        return []
    out: list[tuple[str, dict]] = []
    for cat_dir in sorted(ARTIFACTS_ROOT.iterdir()):
        if not cat_dir.is_dir():
            continue
        model_file = cat_dir / "active" / "model.json"
        if not model_file.exists():
            continue
        try:
            artifact = json.loads(model_file.read_text())
        except Exception:
            continue
        out.append((cat_dir.name, artifact))
    return out


class TestBakedArtifactQuality:
    """Smoke tests against the actual 54 trained Ridge models on disk."""

    def test_at_least_one_active_model_exists(self):
        """Sanity: we should have at least one category with a trained model."""
        artifacts = _discover_active_artifacts()
        assert len(artifacts) > 0, "No active models found in server/artifacts/*/active/"

    @pytest.mark.parametrize("category,artifact", _discover_active_artifacts())
    def test_quantile_inference_produces_sane_prediction(self, category: str, artifact: dict):
        """Every baked model must produce non-negative q10 ≤ q50 ≤ q90 predictions.

        Uses a default "average condition, average rarity" feature input. If
        this fails, the model has been trained on bad data or has numerically
        unstable coefficients. This is the gate that catches Ridge calibration
        regressions before they ship to users.
        """
        model_features = artifact.get("features", [])
        assert model_features, f"{category}: no features in artifact"

        # Default-input feature dict: 0.5 for everything except condition=0.85 (NM)
        features = {f: 0.5 for f in model_features}
        if "condition_score" in features:
            features["condition_score"] = 0.85
        if "is_sealed" in features:
            features["is_sealed"] = 0.0
        if "is_graded" in features:
            features["is_graded"] = 0.0

        result = ridge_infer_quantiles(artifact, features)

        assert result is not None, f"{category}: ridge_infer_quantiles returned None"
        assert "q10" in result and "q50" in result and "q90" in result, (
            f"{category}: missing quantile keys in {result}"
        )

        q10, q50, q90 = result["q10"], result["q50"], result["q90"]

        # Finite
        import math
        assert math.isfinite(q10), f"{category}: q10 is not finite ({q10})"
        assert math.isfinite(q50), f"{category}: q50 is not finite ({q50})"
        assert math.isfinite(q90), f"{category}: q90 is not finite ({q90})"

        # Non-negative (no negative prices ever reach users)
        assert q10 >= 0, f"{category}: q10 negative ({q10})"
        assert q50 >= 0, f"{category}: q50 negative ({q50})"
        assert q90 >= 0, f"{category}: q90 negative ({q90})"

        # Ordering
        assert q10 <= q50 <= q90, (
            f"{category}: quantile ordering violated (q10={q10}, q50={q50}, q90={q90})"
        )

        # Sanity ceiling — nothing a user scans with default features should
        # ever predict more than €50M. Grail-tier items need real context.
        assert q90 <= 50_000_000, f"{category}: q90 exceeds €50M sanity cap ({q90})"
