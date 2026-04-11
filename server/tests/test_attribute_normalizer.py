"""
Tests for app/ml/attribute_normalizer.py — fuzzy matching of vision-extracted
attributes against the catalog vocabulary.
"""

import json
from unittest.mock import patch

from app.ml.attribute_normalizer import (
    _levenshtein,
    normalize_value,
    normalize_attributes,
    reload_vocab,
)


# ---------------------------------------------------------------------------
# Levenshtein
# ---------------------------------------------------------------------------

class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("abc", "abc") == 0

    def test_single_edit(self):
        assert _levenshtein("kitten", "sitten") == 1
        assert _levenshtein("rolex", "rolexx") == 1

    def test_classic_kitten_sitting(self):
        assert _levenshtein("kitten", "sitting", max_dist=10) == 3

    def test_empty_strings(self):
        assert _levenshtein("", "") == 0
        assert _levenshtein("abc", "") == 3
        assert _levenshtein("", "abc") == 3

    def test_max_dist_bailout(self):
        # Strings far apart return max_dist+1
        assert _levenshtein("abcdef", "ghijkl", max_dist=2) == 3


# ---------------------------------------------------------------------------
# normalize_value (with mocked vocab)
# ---------------------------------------------------------------------------

MOCK_VOCAB = {
    "watches": {
        "brand": {"Rolex": 124, "Omega": 78, "Tudor": 32, "Audemars Piguet": 15},
        "case_material": {"Stainless Steel": 412, "18k Yellow Gold": 21, "Titanium": 8},
    },
    "pokemon": {
        "set_name": {"Base Set": 102, "Jungle": 64, "Fossil": 50, "Team Rocket": 30},
    },
}


def _setup_mock_vocab():
    reload_vocab()
    from app.ml import attribute_normalizer
    attribute_normalizer._load_vocab.cache_clear()
    attribute_normalizer._load_brand_registry.cache_clear()
    # Patch the loaders to return our mock vocab + empty brand registry
    attribute_normalizer._load_vocab = lambda: MOCK_VOCAB  # type: ignore
    attribute_normalizer._load_brand_registry = lambda: {}  # type: ignore


def _teardown_mock_vocab():
    from app.ml import attribute_normalizer
    # Restore the original function
    import importlib
    importlib.reload(attribute_normalizer)


class TestNormalizeValue:
    def setup_method(self):
        _setup_mock_vocab()

    def teardown_method(self):
        _teardown_mock_vocab()

    def test_exact_match(self):
        normalized, match = normalize_value("watches", "brand", "Rolex")
        assert normalized == "Rolex"
        assert match == "exact"

    def test_case_insensitive_match(self):
        normalized, match = normalize_value("watches", "brand", "rolex")
        assert normalized == "Rolex"
        assert match == "case"

        normalized, match = normalize_value("watches", "brand", "OMEGA")
        assert normalized == "Omega"
        assert match == "case"

    def test_substring_match(self):
        # "Audemars" is contained in "Audemars Piguet"
        normalized, match = normalize_value("watches", "brand", "Audemars")
        assert normalized == "Audemars Piguet"
        assert match == "substring"

    def test_fuzzy_match_typo(self):
        # 1 edit distance: "Rolexx" → "Rolex"
        normalized, match = normalize_value("watches", "brand", "Rolexx")
        # Could be substring or fuzzy depending on order; both acceptable
        assert normalized == "Rolex"
        assert match in {"substring", "fuzzy"}

    def test_no_match_keeps_original(self):
        normalized, match = normalize_value("watches", "brand", "UnknownBrand")
        assert normalized == "UnknownBrand"
        assert match is None

    def test_unknown_category_passthrough(self):
        normalized, match = normalize_value("nonexistent", "brand", "Rolex")
        assert normalized == "Rolex"
        assert match is None

    def test_unknown_field_passthrough(self):
        normalized, match = normalize_value("watches", "nonexistent_field", "Anything")
        assert normalized == "Anything"
        assert match is None

    def test_none_value(self):
        normalized, match = normalize_value("watches", "brand", None)
        assert normalized is None
        assert match is None

    def test_non_string_passthrough(self):
        normalized, match = normalize_value("watches", "year", 2024)
        assert normalized == 2024
        assert match is None

    def test_pokemon_set_name(self):
        normalized, match = normalize_value("pokemon", "set_name", "base set")
        assert normalized == "Base Set"
        assert match == "case"


class TestNormalizeAttributes:
    def setup_method(self):
        _setup_mock_vocab()

    def teardown_method(self):
        _teardown_mock_vocab()

    def test_full_dict(self):
        raw = {"brand": "rolex", "case_material": "stainless steel"}
        normalized, log = normalize_attributes("watches", raw)
        assert normalized["brand"] == "Rolex"
        assert normalized["case_material"] == "Stainless Steel"
        assert "brand" in log
        assert "case_material" in log

    def test_mixed_match_and_passthrough(self):
        raw = {"brand": "Rolex", "model": "Submariner"}  # model not in vocab
        normalized, log = normalize_attributes("watches", raw)
        assert normalized["brand"] == "Rolex"
        assert normalized["model"] == "Submariner"
        # "model" not in log because no match found

    def test_empty_input(self):
        normalized, log = normalize_attributes("watches", {})
        assert normalized == {}
        assert log == {}
