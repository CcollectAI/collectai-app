"""Tests for the intake agent sub-package split.

Verifies:
- Backward-compatible shim (app.agents.intake_agent) still works
- Direct import from sub-package (app.agents.intake) works
- Helper functions: _normalize_for_search, _text_similarity, _price_band_to_dict
- IntakeResult dataclass has expected fields
- TAXONOMY_VERSION constant exists and is a string
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Import tests — backward compat shim
# ---------------------------------------------------------------------------

class TestBackwardCompatShim:
    """The old import path must still work after the split."""

    def test_process_intake_importable_from_shim(self):
        from app.agents.intake_agent import process_intake
        assert callable(process_intake)

    def test_intake_result_importable_from_shim(self):
        from app.agents.intake_agent import IntakeResult
        assert IntakeResult is not None

    def test_taxonomy_version_importable_from_shim(self):
        from app.agents.intake_agent import TAXONOMY_VERSION
        assert isinstance(TAXONOMY_VERSION, str)

    def test_process_url_import_importable_from_shim(self):
        from app.agents.intake_agent import process_url_import
        assert callable(process_url_import)


# ---------------------------------------------------------------------------
# Import tests — direct sub-package
# ---------------------------------------------------------------------------

class TestDirectSubpackageImport:
    """Imports from app.agents.intake should work identically."""

    def test_process_intake_from_subpackage(self):
        from app.agents.intake import process_intake
        assert callable(process_intake)

    def test_intake_result_from_subpackage(self):
        from app.agents.intake import IntakeResult
        assert IntakeResult is not None

    def test_taxonomy_version_from_subpackage(self):
        from app.agents.intake import TAXONOMY_VERSION
        assert isinstance(TAXONOMY_VERSION, str)

    def test_shim_and_subpackage_are_same_objects(self):
        from app.agents.intake_agent import process_intake as shim_fn
        from app.agents.intake import process_intake as pkg_fn
        assert shim_fn is pkg_fn

    def test_helpers_importable(self):
        from app.agents.intake.helpers import (
            _normalize_for_search,
            _text_similarity,
            _price_band_to_dict,
            IntakeResult,
            TAXONOMY_VERSION,
            CORRECTION_THRESHOLD,
        )
        assert all(x is not None for x in [
            _normalize_for_search, _text_similarity, _price_band_to_dict,
            IntakeResult, TAXONOMY_VERSION, CORRECTION_THRESHOLD,
        ])


# ---------------------------------------------------------------------------
# TAXONOMY_VERSION constant
# ---------------------------------------------------------------------------

class TestTaxonomyVersion:
    def test_exists_and_is_string(self):
        from app.agents.intake.helpers import TAXONOMY_VERSION
        assert isinstance(TAXONOMY_VERSION, str)
        assert len(TAXONOMY_VERSION) > 0

    def test_follows_version_format(self):
        from app.agents.intake.helpers import TAXONOMY_VERSION
        assert TAXONOMY_VERSION.startswith("v")


# ---------------------------------------------------------------------------
# IntakeResult dataclass
# ---------------------------------------------------------------------------

class TestIntakeResult:
    def test_default_construction(self):
        from app.agents.intake.helpers import IntakeResult
        result = IntakeResult()
        assert result.name is None
        assert result.category_id is None
        assert result.category_confidence == 0.0
        assert result.attributes == {}
        assert result.identification_method == "manual"
        assert result.catalog_miss is False
        assert result.alternatives == []
        assert result.rationale == []

    def test_expected_fields_present(self):
        from app.agents.intake.helpers import IntakeResult
        result = IntakeResult()
        expected_fields = [
            "name", "category_id", "category_confidence", "subtype_id",
            "attributes", "identification_method", "barcode", "barcode_type",
            "taxonomy_version", "taxonomy_confidence", "suggested_corrections",
            "estimated_price", "price_source", "price_band", "image_url",
            "catalog_miss", "catalog_match_id", "catalog_match_key",
            "alternatives", "field_confidence", "chain_of_thought",
            "rationale", "scan_session_id", "defect_annotations",
            "suggested_grade", "social_proof", "duplicate_info",
        ]
        for field_name in expected_fields:
            assert hasattr(result, field_name), f"Missing field: {field_name}"

    def test_to_dict_returns_dict(self):
        from app.agents.intake.helpers import IntakeResult
        result = IntakeResult(name="Test Card", category_id="pokemon")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "Test Card"
        assert d["category_id"] == "pokemon"

    def test_to_dict_includes_all_keys(self):
        from app.agents.intake.helpers import IntakeResult
        result = IntakeResult()
        d = result.to_dict()
        assert "name" in d
        assert "category_id" in d
        assert "rationale" in d
        assert "defect_annotations" in d
        assert "social_proof" in d
        assert "duplicate_info" in d

    def test_construction_with_kwargs(self):
        from app.agents.intake.helpers import IntakeResult
        result = IntakeResult(
            name="Charizard Base Set",
            category_id="pokemon",
            category_confidence=0.95,
            estimated_price=350.0,
            price_source="market",
            catalog_miss=True,
        )
        assert result.name == "Charizard Base Set"
        assert result.category_confidence == 0.95
        assert result.estimated_price == 350.0
        assert result.catalog_miss is True


# ---------------------------------------------------------------------------
# _normalize_for_search
# ---------------------------------------------------------------------------

class TestNormalizeForSearch:
    def test_lowercases(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("HELLO WORLD") == "hello world"

    def test_strips_punctuation(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("Hello, World!") == "hello world"

    def test_strips_whitespace(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("  hello   world  ") == "hello world"

    def test_truncates_to_100_chars(self):
        from app.agents.intake.helpers import _normalize_for_search
        long_input = "a " * 200
        result = _normalize_for_search(long_input)
        assert len(result) <= 100

    def test_removes_special_chars(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("test@#$%item") == "testitem"

    def test_preserves_numbers(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("Pokemon #25") == "pokemon 25"

    def test_empty_string(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("") == ""

    def test_only_punctuation(self):
        from app.agents.intake.helpers import _normalize_for_search
        assert _normalize_for_search("!!!???...") == ""


# ---------------------------------------------------------------------------
# _text_similarity
# ---------------------------------------------------------------------------

class TestTextSimilarity:
    def test_identical_strings(self):
        from app.agents.intake.helpers import _text_similarity
        assert _text_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        from app.agents.intake.helpers import _text_similarity
        assert _text_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        from app.agents.intake.helpers import _text_similarity
        score = _text_similarity("pokemon base set charizard", "charizard base set")
        # Overlap: {charizard, base, set} = 3, Union: {pokemon, charizard, base, set} = 4
        assert abs(score - 3 / 4) < 0.01

    def test_case_insensitive(self):
        from app.agents.intake.helpers import _text_similarity
        assert _text_similarity("Hello World", "hello world") == 1.0

    def test_empty_string_returns_zero(self):
        from app.agents.intake.helpers import _text_similarity
        assert _text_similarity("", "hello") == 0.0
        assert _text_similarity("hello", "") == 0.0
        assert _text_similarity("", "") == 0.0

    def test_symmetry(self):
        from app.agents.intake.helpers import _text_similarity
        a = "pokemon charizard holo"
        b = "charizard holo rare"
        assert _text_similarity(a, b) == _text_similarity(b, a)


# ---------------------------------------------------------------------------
# _price_band_to_dict
# ---------------------------------------------------------------------------

class TestPriceBandToDict:
    def test_dict_passthrough(self):
        from app.agents.intake.helpers import _price_band_to_dict
        d = {"q10": 10, "q50": 50, "q90": 90, "confidence": 0.8, "currency": "EUR"}
        assert _price_band_to_dict(d) == d

    def test_pydantic_v2_model_dump(self):
        from app.agents.intake.helpers import _price_band_to_dict

        class FakePydanticV2:
            def model_dump(self):
                return {"q10": 5, "q50": 25, "q90": 50}

        result = _price_band_to_dict(FakePydanticV2())
        assert result == {"q10": 5, "q50": 25, "q90": 50}

    def test_pydantic_v1_dict(self):
        from app.agents.intake.helpers import _price_band_to_dict

        class FakePydanticV1:
            def dict(self):
                return {"q10": 10, "q50": 30, "q90": 60}

        result = _price_band_to_dict(FakePydanticV1())
        assert result == {"q10": 10, "q50": 30, "q90": 60}

    def test_fallback_to_getattr(self):
        from app.agents.intake.helpers import _price_band_to_dict

        class PlainObj:
            q10 = 1
            q50 = 5
            q90 = 10
            confidence = 0.5
            currency = "USD"

        result = _price_band_to_dict(PlainObj())
        assert result["q10"] == 1
        assert result["q50"] == 5
        assert result["q90"] == 10
        assert result["confidence"] == 0.5
        assert result["currency"] == "USD"
