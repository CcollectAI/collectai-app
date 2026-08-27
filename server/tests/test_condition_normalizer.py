"""`normalize_condition` — one vocabulary for a column that has many.

Every value in OBSERVED was read out of prod `market_hits.condition`, not
invented: `Neu` and `Nicht bewertet` are German rows from a live adapter, and
`NM` is 2,926,015 of the 2,927,565 sold comps in the last 90 days.

Nothing filters on the output yet. This is prep so that grade-matched comps —
the thing collectors actually ask for — become a query later rather than a
data-cleaning project.
"""
import pytest

from app.lib.condition_normalizer import normalize_condition, UNKNOWN


@pytest.mark.parametrize("raw", ["New", "new", "Brand New", "New/Factory Sealed", "Neu", "Sealed"])
def test_case_and_language_variants_collapse_to_sealed(raw):
    assert normalize_condition(raw) == "sealed"


@pytest.mark.parametrize("raw", ["used", "Used", "complete-in-box", "unsealed", "not sealed"])
def test_used_variants(raw):
    assert normalize_condition(raw) == "used"


@pytest.mark.parametrize("raw", ["NM", "Ungraded", "Nicht bewertet", "heavily played"])
def test_ungraded_singles_are_raw_not_a_grade(raw):
    # A seller's "NM" is a claim, not a certification. Treating it as
    # comparable to a PSA 9 is the raw-vs-certified conflation this exists to
    # make avoidable.
    assert normalize_condition(raw) == "raw"


@pytest.mark.parametrize("raw,want", [
    ("PSA 9", "graded:psa:9"),
    ("PSA10", "graded:psa:10"),
    ("psa 10", "graded:psa:10"),
    ("BGS 9.5", "graded:bgs:9.5"),
    ("CGC 8", "graded:cgc:8"),
    ("SGC 9.0", "graded:sgc:9"),   # trailing .0 must not form a second bucket
])
def test_certified_grades(raw, want):
    assert normalize_condition(raw) == want


@pytest.mark.parametrize("raw", ["PSA", "graded", "Graded"])
def test_certified_without_a_grade_is_not_raw(raw):
    assert normalize_condition(raw) == "graded:unknown:unknown"


@pytest.mark.parametrize("raw", [None, "", "   ", "???"])
def test_unknown_is_explicit(raw):
    assert normalize_condition(raw) == UNKNOWN


def test_grade_wins_over_a_condition_word_in_the_same_string():
    # "PSA 9 mint" is a graded card, not a raw one.
    assert normalize_condition("PSA 9 mint") == "graded:psa:9"
