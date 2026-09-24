"""Catalog rows that share a title must not produce a confident, arbitrary identity.

2026-09-24: /catalog/match returned FIVE pokemon "Charizard ex" rows at score
1.0 and `best` was the first (sv4pt5-234) — even with set_code "svp" sent. That
key prices the item and decides which Target Hit watchers are alerted: the
member watching SVP #161 would never hear of a seller's #161, and a watcher of
#234 would be alerted for the wrong card.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.intake.catalog_matching import resolve_title_ties  # noqa: E402

FIVE = [
    {"item_key": k, "match_score": 1.0, "set_code": s}
    for k, s in [
        ("sv4pt5-sv4pt5-234", "sv4pt5"), ("sv3-sv3-125", "sv3"), ("sv4pt5-sv4pt5-54", "sv4pt5"),
        ("svp-svp-161", "svp"), ("sv3pt5-sv3pt5-6", "sv3pt5"),
    ]
]


def test_unresolved_tie_is_flagged_and_capped_below_every_writer():
    out, ambiguous = resolve_title_ties(FIVE, None, None)
    assert ambiguous
    assert all(m["match_score"] < 0.6 and m["ambiguous"] for m in out)


def test_card_number_picks_the_card():
    out, ambiguous = resolve_title_ties(FIVE, None, "161")
    assert not ambiguous and out[0]["item_key"] == "svp-svp-161" and out[0]["match_score"] == 1.0


def test_number_with_a_set_total_and_leading_zeros():
    out, ambiguous = resolve_title_ties(FIVE, "sv4pt5", "054/091")
    assert not ambiguous and out[0]["item_key"] == "sv4pt5-sv4pt5-54"


def test_set_code_alone_resolves_when_unique():
    out, ambiguous = resolve_title_ties(FIVE, "svp", None)
    assert not ambiguous and out[0]["item_key"] == "svp-svp-161"


def test_set_code_that_still_leaves_two_is_ambiguous():
    _, ambiguous = resolve_title_ties(FIVE, "sv4pt5", None)
    assert ambiguous


def test_a_clear_winner_is_untouched():
    rows = [{"item_key": "a", "match_score": 1.0}, {"item_key": "b", "match_score": 0.7}]
    out, ambiguous = resolve_title_ties(rows, None, None)
    assert not ambiguous and out == rows
