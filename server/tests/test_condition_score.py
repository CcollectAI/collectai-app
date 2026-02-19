"""Tests for _condition_to_score in vision_predict.py (Item 12)."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.routes.vision_predict import _condition_to_score


class TestConditionToScore:
    def test_none_returns_none(self):
        assert _condition_to_score(None) is None

    def test_empty_returns_none(self):
        assert _condition_to_score("") is None

    def test_mint(self):
        assert _condition_to_score("mint") == 0.95

    def test_gem_mint(self):
        assert _condition_to_score("gem mint") == 0.95

    def test_near_mint(self):
        assert _condition_to_score("near_mint") == 0.85

    def test_near_mint_nm(self):
        assert _condition_to_score("NM") == 0.85

    def test_excellent(self):
        assert _condition_to_score("excellent") == 0.75

    def test_very_good(self):
        assert _condition_to_score("very_good") == 0.65

    def test_good(self):
        assert _condition_to_score("good") == 0.60

    def test_light_play(self):
        assert _condition_to_score("LP") == 0.60

    def test_played(self):
        assert _condition_to_score("played") == 0.45

    def test_poor(self):
        assert _condition_to_score("poor") == 0.25

    def test_damaged(self):
        assert _condition_to_score("damaged") == 0.25

    def test_unknown_returns_default(self):
        assert _condition_to_score("something_else") == 0.50

    def test_case_insensitive(self):
        assert _condition_to_score("NEAR MINT") == 0.85
        assert _condition_to_score("Gem Mint") == 0.95

    def test_underscore_converted(self):
        # "near_mint" should be treated as "near mint"
        assert _condition_to_score("near_mint") == 0.85
