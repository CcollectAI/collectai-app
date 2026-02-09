"""Tests for routes.py prediction helpers — _attrs_to_features, _model_predict fallback chain."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure the services path is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Mock heavy dependencies before importing routes (top-level imports)
for mod_name in [
    "psycopg2", "psycopg2.extras",
    "fastapi", "fastapi.responses",
    "services.collectors_merge.core.env",
]:
    sys.modules.setdefault(mod_name, MagicMock())

# FastAPI stubs needed by routes.py module-level code
_fastapi = sys.modules["fastapi"]
_fastapi.APIRouter = MagicMock(return_value=MagicMock())
_fastapi.HTTPException = type("HTTPException", (Exception,), {"__init__": lambda self, *a, **kw: None})
_fastapi.File = MagicMock()
_fastapi.Form = MagicMock()
_fastapi.Header = MagicMock()
_fastapi.Response = MagicMock()
_fastapi.UploadFile = MagicMock()

# Mock the env loader to avoid side effects
with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
    from services.collectors_merge.api.routes import (
        _attrs_to_features,
        _model_predict,
        normalized_key,
        to_eur,
        effective_price,
    )


# ---------------------------------------------------------------------------
# _attrs_to_features
# ---------------------------------------------------------------------------

class TestAttrsToFeatures:
    def test_empty_attrs(self):
        f = _attrs_to_features({})
        assert f["condition_score"] == 0.5
        assert f["rarity_score"] == 0.5
        assert f["edition_score"] == 0.5

    def test_condition_mint(self):
        f = _attrs_to_features({"condition": "Mint"})
        assert f["condition_score"] == 0.95

    def test_condition_near_mint(self):
        f = _attrs_to_features({"condition": "Near Mint"})
        assert f["condition_score"] == 0.85

    def test_condition_nm_abbrev(self):
        f = _attrs_to_features({"condition": "NM"})
        assert f["condition_score"] == 0.85

    def test_condition_guess_fallback(self):
        f = _attrs_to_features({"condition_guess": "excellent"})
        assert f["condition_score"] == 0.75

    def test_condition_damaged(self):
        f = _attrs_to_features({"condition": "Damaged"})
        assert f["condition_score"] == 0.15

    def test_condition_unknown_defaults(self):
        f = _attrs_to_features({"condition": "unique_condition"})
        assert f["condition_score"] == 0.5

    def test_grade_psa_10(self):
        f = _attrs_to_features({"grade": "PSA 10"})
        assert f["condition_score"] == 1.0
        assert f.get("is_graded") == 1.0

    def test_grade_psa_7(self):
        f = _attrs_to_features({"grade": "PSA 7"})
        assert f["condition_score"] == 0.7

    def test_grade_overrides_condition(self):
        f = _attrs_to_features({"condition": "Poor", "grade": "BGS 9"})
        assert f["condition_score"] == 0.9

    def test_grade_invalid_keeps_condition(self):
        f = _attrs_to_features({"condition": "Mint", "grade": "UNGRADED"})
        # grade parsing fails → condition_score stays from condition mapping
        assert f["condition_score"] == 0.95

    def test_rarity_score_passthrough(self):
        f = _attrs_to_features({"rarity_score": 0.85})
        assert f["rarity_score"] == 0.85

    def test_rarity_score_defaults(self):
        f = _attrs_to_features({})
        assert f["rarity_score"] == 0.5

    def test_edition_first(self):
        f = _attrs_to_features({"edition": "1st Edition"})
        assert f["edition_score"] == 0.95

    def test_edition_alpha(self):
        f = _attrs_to_features({"edition": "Alpha"})
        assert f["edition_score"] == 0.95

    def test_edition_shadowless(self):
        f = _attrs_to_features({"edition": "Shadowless"})
        assert f["edition_score"] == 0.90

    def test_edition_unlimited(self):
        f = _attrs_to_features({"edition": "Unlimited"})
        assert f["edition_score"] == 0.70

    def test_edition_promo(self):
        f = _attrs_to_features({"edition_guess": "Promo"})
        assert f["edition_score"] == 0.65

    def test_edition_unknown(self):
        f = _attrs_to_features({"edition": "something"})
        assert f["edition_score"] == 0.5

    def test_sealed_flag(self):
        f = _attrs_to_features({"sealed": True})
        assert f.get("is_sealed") == 1.0

    def test_foil_flag(self):
        f = _attrs_to_features({"is_foil": True})
        assert f.get("is_foil") == 1.0

    def test_graded_flag_from_is_graded(self):
        f = _attrs_to_features({"is_graded": True})
        assert f.get("is_graded") == 1.0

    def test_no_boolean_flags_when_absent(self):
        f = _attrs_to_features({})
        assert "is_sealed" not in f
        assert "is_foil" not in f
        assert "is_graded" not in f


# ---------------------------------------------------------------------------
# _model_predict — fallback chain
# ---------------------------------------------------------------------------

class TestModelPredict:
    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_heuristic_fallback_no_model(self, mock_load):
        """When no model and no baseline, use heuristic."""
        mock_load.return_value = None
        with patch("os.path.exists", return_value=False):
            result = _model_predict("pokemon", {})
        assert "q10" in result
        assert "q50" in result
        assert "q90" in result
        assert result["q10"] <= result["q50"] <= result["q90"]

    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_heuristic_psa10_multiplier(self, mock_load):
        mock_load.return_value = None
        with patch("os.path.exists", return_value=False):
            base = _model_predict("pokemon", {})
            graded = _model_predict("pokemon", {"grade": "PSA 10"})
        assert graded["q50"] > base["q50"]

    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_heuristic_sealed_multiplier(self, mock_load):
        mock_load.return_value = None
        with patch("os.path.exists", return_value=False):
            unsealed = _model_predict("pokemon", {})
            sealed = _model_predict("pokemon", {"sealed": True})
        # sealed=True means the 0.9 multiplier is NOT applied
        assert sealed["q50"] > unsealed["q50"]

    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_baseline_model_used_when_available(self, mock_load):
        """When baseline.json exists, use it instead of heuristic."""
        mock_load.return_value = None
        baseline = {"median_by_group": {"sealed=0|grade10=0": 200.0}}
        import builtins
        original_open = builtins.open
        def mock_open(path, *a, **kw):
            if "baseline" in str(path):
                import io
                return io.StringIO(json.dumps(baseline))
            return original_open(path, *a, **kw)

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open):
            result = _model_predict("pokemon", {})
        assert result["q50"] == 200.0
        assert result["q10"] == round(200.0 * 0.8, 2)
        assert result["q90"] == round(200.0 * 1.2, 2)

    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_ridge_model_used_when_available(self, mock_load):
        """When ridge model returns quantiles, use them."""
        mock_load.return_value = {"model_type": "ridge_v2", "features": ["condition_score"]}
        with patch("inference.ridge_infer_quantiles", return_value={"q10": 10, "q50": 50, "q90": 90}):
            result = _model_predict("pokemon", {})
        assert result == {"q10": 10, "q50": 50, "q90": 90}

    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_ridge_failure_falls_to_heuristic(self, mock_load):
        """When ridge model fails, fall through to heuristic."""
        mock_load.return_value = {"model_type": "ridge_v2", "features": ["condition_score"]}
        with patch("inference.ridge_infer_quantiles", side_effect=Exception("broken")), \
             patch("os.path.exists", return_value=False):
            result = _model_predict("pokemon", {})
        assert "q50" in result  # heuristic kicked in
        assert result["q10"] <= result["q50"] <= result["q90"]

    @patch("services.collectors_merge.api.routes._load_model_artifact")
    def test_all_results_non_negative(self, mock_load):
        mock_load.return_value = None
        with patch("os.path.exists", return_value=False):
            result = _model_predict("pokemon", {})
        assert result["q10"] >= 0
        assert result["q50"] >= 0
        assert result["q90"] >= 0


# ---------------------------------------------------------------------------
# normalized_key
# ---------------------------------------------------------------------------

class TestNormalizedKey:
    def test_lego_with_set_no(self):
        attrs = {"set_no": "75192", "piece_count": 7541, "retired": True, "sealed": False}
        result = normalized_key("lego", attrs)
        assert "lego|75192" in result
        assert "pcs:7541" in result
        assert "ret:1" in result
        assert "s:0" in result

    def test_lego_case_insensitive(self):
        attrs = {"set_no": "10297"}
        result = normalized_key("LEGO", attrs)
        assert "lego|10297" in result

    def test_generic_category_fallback(self):
        result = normalized_key("pokemon", {})
        assert result == "pokemon|fallback"

    def test_empty_category(self):
        result = normalized_key("", {})
        assert result == "misc|fallback"

    def test_none_category(self):
        result = normalized_key(None, {})
        assert result == "misc|fallback"


# ---------------------------------------------------------------------------
# Simple helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_to_eur_passthrough(self):
        assert to_eur(100, "EUR") == 100.0

    def test_to_eur_none_defaults(self):
        assert to_eur(None, "EUR") == 0.0

    def test_effective_price(self):
        assert effective_price("tcgplayer", 10.50, 3.99) == 14.49

    def test_effective_price_none_values(self):
        assert effective_price("tcgplayer", None, None) == 0.0
