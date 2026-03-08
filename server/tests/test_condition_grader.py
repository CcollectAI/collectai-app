"""Tests for condition grading utilities."""
import pytest
from app.ml.condition_grader import (
    map_defects_to_psa_grade,
    map_defects_to_cgc_grade,
    defects_to_generic_condition,
)


def test_psa_gem_mint_no_defects():
    result = map_defects_to_psa_grade([])
    assert result["grade"] == 10
    assert result["label"] == "Gem Mint"


def test_psa_with_minor_defects():
    defects = [{"severity": "minor"}, {"severity": "minor"}]
    result = map_defects_to_psa_grade(defects)
    assert result["grade"] >= 8  # 1.0 defect score -> NM-M (8)


def test_cgc_no_defects():
    result = map_defects_to_cgc_grade([])
    assert result["grade"] == 9.8
    assert result["label"] == "Near Mint/Mint"


def test_cgc_with_moderate_defects():
    defects = [{"severity": "moderate"}, {"severity": "minor"}]
    result = map_defects_to_cgc_grade(defects)
    assert result["grade"] <= 9.4


def test_generic_condition_no_defects():
    result = defects_to_generic_condition([])
    assert result["condition"] == "mint"


def test_generic_condition_major_defects():
    defects = [{"severity": "major"}, {"severity": "major"}, {"severity": "moderate"}]
    result = defects_to_generic_condition(defects)
    assert result["condition"] in ("good", "fair", "poor")
