"""PriceCharting is the only source whose rows carry a real `ended_at`.

Expanded from 4 categories to 10 on 2026-08-31. Every addition was PROBED
against the live adapter first and every console token was READ from an observed
response — `learning_dont_allowlist_dead_assert_dead`, and
`learning_keyless_pricecharting_needs_console_guard` for why a guard built from a
guess is worse than none.
"""
from app.agents.adapters.pricecharting_caller import (
    SUPPORTED_CATEGORIES, _CATEGORY_CONSOLE_ALLOW,
)
from app.agents.marketplace_routing import ADAPTER_CATEGORY_ROUTING, DISABLED_ADAPTERS

ROUTED = ADAPTER_CATEGORY_ROUTING["pricecharting"]


class TestTheListThatActuallyRoutes:
    """The adapter's SUPPORTED_CATEGORIES gates NOTHING.

    Found by auditing the first version of this change on 2026-08-31: six
    categories were added to `SUPPORTED_CATEGORIES`, which no module reads, and
    the change routed nothing. The real gate is
    `ADAPTER_CATEGORY_ROUTING["pricecharting"]`. Editing a list that shares the
    concept but is not the one consumed is
    feedback_same_name_is_not_the_same_thing, and these tests exist so the next
    edit cannot land on the decoy.
    """

    def test_the_two_lists_agree(self):
        assert set(SUPPORTED_CATEGORIES) == ROUTED, (
            "SUPPORTED_CATEGORIES documents the adapter; ADAPTER_CATEGORY_ROUTING "
            "gates it. They must not drift -- a category in the doc list only is "
            "a change that does nothing."
        )

    def test_the_probed_categories_are_ROUTED_not_merely_listed(self):
        for c in ("mtg", "yugioh", "lorcana", "one_piece_tcg", "comic_books", "funko"):
            assert c in ROUTED, f"{c} probed live but is not routed"

    def test_SPORTSCARDS_IS_NOT_ROUTED(self):
        """It was, and it returns zero results.

        Routed since the adapter was written, so every sportscards lookup paid a
        request and got nothing back. Probed 2026-08-31 with "1986 Fleer Michael
        Jordan": 0 results.
        """
        assert "sportscards" not in ROUTED

    def test_the_adapter_is_not_disabled(self):
        # Routing a category to a disabled adapter is a third way for this to
        # look configured and do nothing.
        assert "pricecharting" not in DISABLED_ADAPTERS


class TestTheAllowlist:
    def test_the_probed_categories_are_enabled(self):
        for c in ("mtg", "yugioh", "lorcana", "one_piece_tcg", "comic_books", "funko"):
            assert c in SUPPORTED_CATEGORIES, f"{c} was probed and returned results"

    def test_the_original_four_survive(self):
        for c in ("retro_games", "retro_handhelds", "pokemon", "nintendo_merch"):
            assert c in SUPPORTED_CATEGORIES

    def test_SPORTSCARDS_STAYS_OUT(self):
        """Probed 2026-08-31: "1986 Fleer Michael Jordan" -> ZERO results.

        An allowlist entry for a dead source is indistinguishable from a working
        one until somebody measures it, which is the whole reason this test
        names it rather than leaving its absence to be re-litigated.
        """
        assert "sportscards" not in SUPPORTED_CATEGORIES


class TestTheConsoleGuards:
    def test_every_guarded_category_is_actually_enabled(self):
        # A guard for a category nobody queries is dead configuration.
        for cat in _CATEGORY_CONSOLE_ALLOW:
            assert cat in SUPPORTED_CATEGORIES, (
                f"{cat} has a console guard but is not in SUPPORTED_CATEGORIES"
            )

    def test_the_tcgs_are_guarded_against_cross_database_bleed(self):
        """Layer 1 exists because a Pokemon search returned a Yugioh card.

        Adding six categories to one keyless search endpoint multiplies that
        risk, so each carries a token taken from a REAL console value.
        """
        for cat in ("mtg", "yugioh", "lorcana", "one_piece_tcg"):
            assert cat in _CATEGORY_CONSOLE_ALLOW, f"{cat} needs a console guard"

    def test_tokens_match_the_consoles_actually_observed(self):
        observed = {
            "mtg": "Magic Alpha",
            "yugioh": "Yugioh Legend Of Blue Eyes White Dragon",
            "lorcana": "Lorcana Promo",
            "one_piece_tcg": "One Piece Promo",
            "comic_books": "Comic Books Amazing Spider Man",
            "funko": "Funko Pop Heroes",
        }
        for cat, console in observed.items():
            tokens = _CATEGORY_CONSOLE_ALLOW[cat]
            assert any(t in console.lower() for t in tokens), (
                f"{cat}: none of {tokens} appears in the observed console "
                f"{console!r} — the guard would drop every real result"
            )

    def test_tokens_are_lowercase(self):
        # They are matched against a lowercased console path segment.
        for cat, tokens in _CATEGORY_CONSOLE_ALLOW.items():
            for t in tokens:
                assert t == t.lower(), f"{cat} token {t!r} would never match"
