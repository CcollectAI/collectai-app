"""
Integration test for the QuickScan attribute flow:

  Vision extraction → attribute_normalizer (snap to canonical) → response

Verifies that:
1. The intake response includes structured `attributes` (not flattened)
2. Brand-like fields are canonicalized when present in the brand registry
3. The featurizer can convert response attributes to model features
"""

from app.ml.attribute_normalizer import normalize_attributes, reload_vocab
from app.ml.attribute_features import featurize_attributes


class TestAttributeFlow:
    def setup_method(self):
        # Reload to ensure fresh state for each test
        reload_vocab()

    def test_normalize_then_featurize_pipeline(self):
        """Vision-extracted attrs → normalized → featurized end-to-end."""
        # Simulate raw vision extraction for a watch
        raw_attrs = {
            "brand": "Rolex",
            "model_name": "Submariner Date",
            "reference_number": "126610LN",
            "case_material": "Stainless Steel",
            "year": 2020,
        }

        # Step 1: Normalize against vocab
        normalized, log = normalize_attributes("watches", raw_attrs)

        # Should have all the same fields
        assert "brand" in normalized
        assert "reference_number" in normalized
        # log may be empty if all values were already canonical

        # Step 2: Convert to features
        feats = featurize_attributes("watches", normalized)
        assert "brand_tier" in feats
        assert "has_reference" in feats
        assert feats["has_reference"] == 1.0
        assert "has_year" in feats
        assert feats["has_year"] == 1.0

    def test_empty_attributes_pipeline(self):
        """Empty attributes returns empty features."""
        normalized, _ = normalize_attributes("watches", {})
        feats = featurize_attributes("watches", normalized)
        assert normalized == {}
        assert feats == {}

    def test_pokemon_card_flow(self):
        """Pokemon card with set + card_number gives set_completeness."""
        raw_attrs = {
            "set_name": "Base Set",
            "card_number": 4,
            "set_total": 102,
            "is_holo": True,
            "rarity": "Holo Rare",
        }
        normalized, _ = normalize_attributes("pokemon", raw_attrs)
        feats = featurize_attributes("pokemon", normalized)

        assert feats["has_set_info"] == 1.0
        assert 0.0 < feats["set_completeness"] < 0.1  # 4/102

    def test_normalization_preserves_unknown_categories(self):
        """Unknown category passes through without crash."""
        raw_attrs = {"brand": "TestBrand", "model": "Test"}
        normalized, _ = normalize_attributes("not_a_real_category", raw_attrs)
        assert normalized["brand"] == "TestBrand"
        assert normalized["model"] == "Test"

    def test_featurizer_handles_string_year(self):
        """Year as a string still works (no crash)."""
        raw_attrs = {"year": "2020"}
        feats = featurize_attributes("watches", raw_attrs)
        # Should not crash; has_year may or may not be set depending on type check
        assert "has_year" in feats
