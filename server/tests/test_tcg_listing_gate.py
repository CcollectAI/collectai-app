"""TCG listing gate — real titles stored under the wrong card (2026-10-15).

Rows that passed the gate and landed under `pokemon:svp-svp-161` (Charizard ex
Black Star Promo 161), firing Target Hits on a €30 watch, plus a sample of
other Pokémon rows lacking the card number. A false positive here is a wrong
paid alert AND a wrong price comp.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workers.marketplace_scrape_scheduler import (  # noqa: E402
    _NUMBER_REQUIRED_CATEGORIES,
    _collector_number,
    _is_plausible_tcg_listing,
    _printing_matches,
)


def _keep(title, card="Charizard ex", key="svp-svp-161", cat="pokemon"):
    return (_is_plausible_tcg_listing(title, card, cat)
            and _printing_matches(title, _collector_number(key),
                                  require=cat in _NUMBER_REQUIRED_CATEGORIES))


@pytest.mark.parametrize("title", [
    "Charizard ex 161 Black Star Promo Holo English Pokemon Card TCG NM",
    "Charizard ex 161 Sv: Scarlet & Violet Promo Card Holo Pokemon Tcg",
    "Pokemon TCG Charizard ex 161 SV Promo Holo Promo EX 330 HP Stage 2 EN",
])
def test_the_watched_card_is_kept(title):
    assert _keep(title)


@pytest.mark.parametrize("title", [
    "Pokemon TCG Phantasmal Flames Mega Charizard EX UPC (No Cards)",
    "Mega Charizard Y EX - Pokemon TCG Pocket - Full Art - English",
    "Pokemon TCG Charizard Ex",                                   # no number
    "Pokémon TCG Charizard EX Scarlet & Violet Promo Card Holo NM Condition",
])
def test_wrong_or_unprovable_listings_are_rejected(title):
    assert not _keep(title)


@pytest.mark.parametrize("title,card", [
    ("Pokémon TCG Gyarados VMAX *Fan Art* Full Art Holo 34", "Gyarados VMAX"),
    ("Pokémon TCG -Thicc Snorlax NOT REAL meme Card (Unofficial Parody-NOT PSA Graded) 77", "Snorlax"),
])
def test_fan_made_cards_are_rejected_even_with_a_number(title, card):
    assert not _is_plausible_tcg_listing(title, card, "pokemon")


def test_mtg_keeps_the_lenient_number_rule():
    # Sellers omit collector numbers on MTG (59% quote them); the 2026-08-06
    # rule stays: no number = cannot disprove = accept.
    assert _printing_matches("NM Talisman of Impulse, MTG, Tarkir Dragonstorm",
                             _collector_number("tdc-332-talisman-of-impulse"),
                             require="mtg" in _NUMBER_REQUIRED_CATEGORIES)
