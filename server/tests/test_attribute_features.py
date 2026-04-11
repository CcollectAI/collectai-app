"""
Tests for app/ml/attribute_features.py — converting structured attributes
into Ridge-friendly numeric features.
"""

from app.ml.attribute_features import (
    featurize_attributes,
    merge_with_core,
    _extract_set_completeness,
    _extract_set_age_years,
    _is_limited_edition,
    _is_graded,
)


class TestFeaturizeBasic:
    def test_empty_returns_empty(self):
        assert featurize_attributes("watches", {}) == {}
        assert featurize_attributes("watches", None) == {}

    def test_returns_all_expected_keys(self):
        feats = featurize_attributes("watches", {"brand": "Rolex"})
        expected = {
            "brand_tier", "has_set_info", "has_reference", "has_year",
            "has_movement", "set_completeness", "set_age_years_norm",
            "is_limited_edition", "is_graded", "piece_count_log",
        }
        assert set(feats.keys()) == expected

    def test_all_features_are_floats(self):
        feats = featurize_attributes("pokemon", {
            "set_name": "Base Set", "card_number": 4, "set_total": 102,
        })
        for k, v in feats.items():
            assert isinstance(v, float), f"{k}={v} is not float"

    def test_features_in_range_0_to_1(self):
        feats = featurize_attributes("lego", {
            "theme": "Star Wars", "piece_count": 7541, "year": 2007,
        })
        for k, v in feats.items():
            assert 0.0 <= v <= 1.0, f"{k}={v} out of range"


class TestSetCompleteness:
    def test_card_within_set(self):
        assert _extract_set_completeness({"card_number": 4, "set_total": 102}) == 4/102

    def test_full_set(self):
        assert _extract_set_completeness({"card_number": 102, "set_total": 102}) == 1.0

    def test_missing_either_returns_zero(self):
        assert _extract_set_completeness({"card_number": 4}) == 0.0
        assert _extract_set_completeness({"set_total": 102}) == 0.0
        assert _extract_set_completeness({}) == 0.0

    def test_clamps_above_1(self):
        assert _extract_set_completeness({"card_number": 200, "set_total": 102}) == 1.0


class TestSetAge:
    def test_recent_year(self):
        from datetime import datetime
        result = _extract_set_age_years({"year": datetime.now().year})
        assert result == 0.0

    def test_old_year(self):
        result = _extract_set_age_years({"year": 1975})
        assert result > 0.5  # 50 years old → 1.0

    def test_no_year(self):
        assert _extract_set_age_years({}) == 0.0

    def test_invalid_year(self):
        assert _extract_set_age_years({"year": "not a year"}) == 0.0
        assert _extract_set_age_years({"year": 99}) == 0.0


class TestLimitedEdition:
    def test_explicit_flag(self):
        assert _is_limited_edition({"is_limited_edition": True}) == 1.0

    def test_le_size(self):
        assert _is_limited_edition({"limited_edition_size": 2500}) == 1.0

    def test_keyword_in_value(self):
        assert _is_limited_edition({"edition": "Limited Edition"}) == 1.0
        assert _is_limited_edition({"variant": "Chase"}) == 1.0
        assert _is_limited_edition({"exclusive_tag": "SDCC Exclusive"}) == 1.0

    def test_no_indicator(self):
        assert _is_limited_edition({"brand": "Hasbro"}) == 0.0


class TestGraded:
    def test_graded_field(self):
        assert _is_graded({"graded": True}) == 1.0
        assert _is_graded({"grade_value": 9.5}) == 1.0

    def test_psa_in_value(self):
        assert _is_graded({"description": "PSA 10 Gem Mint"}) == 1.0
        assert _is_graded({"description": "CGC 9.8"}) == 1.0

    def test_not_graded(self):
        assert _is_graded({"brand": "Topps"}) == 0.0


class TestPieceCount:
    def test_lego_log_normalize(self):
        feats_small = featurize_attributes("lego", {"piece_count": 50})
        feats_large = featurize_attributes("lego", {"piece_count": 7000})
        assert feats_small["piece_count_log"] < feats_large["piece_count_log"]

    def test_no_piece_count(self):
        # Empty dict returns empty (early return)
        feats = featurize_attributes("lego", {})
        assert feats == {}
        # Single attribute that's not piece_count → piece_count_log defaults to 0
        feats = featurize_attributes("lego", {"theme": "Star Wars"})
        assert feats["piece_count_log"] == 0.0


class TestMergeWithCore:
    def test_core_takes_precedence(self):
        core = {"condition_score": 0.9, "rarity_score": 0.5, "edition_score": 0.7}
        attrs = {"brand": "Rolex"}
        merged = merge_with_core(core, "watches", attrs)
        assert merged["condition_score"] == 0.9
        assert merged["rarity_score"] == 0.5
        assert merged["edition_score"] == 0.7
        # Attribute features are present alongside
        assert "brand_tier" in merged
        assert "has_set_info" in merged

    def test_no_attrs(self):
        core = {"condition_score": 0.9}
        merged = merge_with_core(core, "watches", None)
        assert merged == core
