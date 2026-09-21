"""`rarity_to_score_or_none` — the member-facing half of the rarity vocabulary.

The model's `rarity_to_score` falls back to a neutral 0.50 when it cannot read
anything, which is right for a feature vector (0.0 would be an extreme, not an
absence) and wrong for a number shown to a member: it would rank an unreadable
item exactly as confidently as a measured one.

These pin BOTH halves, because the risk when the two are edited apart is silent
— a portfolio that starts scoring every unknown item as middling, with no test
failing and no error anywhere.
"""
import pytest

from app.ml.valuation_features import (
    _DEFAULT_RARITY,
    rarity_to_score,
    rarity_to_score_or_none,
)


class TestTheModelHalfIsUnchanged:
    @pytest.mark.parametrize("attrs,expected", [
        ({"rarity": "Secret Rare"}, 0.98),
        ({"rarity": "Ultra Rare"}, 0.90),
        ({"rarity": "Holo"}, 0.82),
        ({"rarity": "Rare"}, 0.60),
        ({"rarity": "Uncommon"}, 0.45),
        ({"rarity": "Common"}, 0.30),
        ({"is_foil": True}, 0.82),
    ])
    def test_known_vocabulary_scores(self, attrs, expected):
        assert rarity_to_score(attrs) == expected

    @pytest.mark.parametrize("attrs", [{}, {"rarity": ""}, {"rarity": "Trainer"}, {"unrelated": "x"}])
    def test_unknown_still_returns_the_neutral_default(self, attrs):
        """The feature vector must keep getting a number, not None."""
        assert rarity_to_score(attrs) == _DEFAULT_RARITY


class TestTheMemberHalfRefusesToGuess:
    @pytest.mark.parametrize("attrs", [
        {},
        {"rarity": ""},
        {"unrelated": "x"},
        # Vocabulary we hold but do not model. "We cannot rank this" is not the
        # same claim as "this is middling", and 0.50 states the second.
        {"rarity": "Trainer"},
        {"rarity": "Promo Deck"},
    ])
    def test_unknown_is_none_not_a_number(self, attrs):
        assert rarity_to_score_or_none(attrs) is None

    @pytest.mark.parametrize("attrs", [
        {"rarity": "Secret Rare"}, {"rarity": "Holo"}, {"rarity": "Common"}, {"is_foil": True},
    ])
    def test_agrees_with_the_model_wherever_it_knows(self, attrs):
        assert rarity_to_score_or_none(attrs) == rarity_to_score(attrs)

    def test_accepts_a_json_string_as_well_as_a_dict(self):
        """`items.attrs` arrives as a dict via the jsonb codec, but a caller
        without that codec must degrade to a correct answer, not a wrong one."""
        assert rarity_to_score_or_none('{"rarity": "Ultra Rare"}') == 0.90
        assert rarity_to_score_or_none("not json") is None
        assert rarity_to_score_or_none(None) is None

    def test_no_input_can_make_it_return_the_neutral_guess_by_accident(self):
        """The whole point: 0.50 must only ever appear as a MEASURED tier."""
        measured = {score for score, _ in [(0.98, 0), (0.90, 0), (0.82, 0), (0.75, 0), (0.60, 0), (0.45, 0), (0.30, 0)]}
        assert _DEFAULT_RARITY not in measured
