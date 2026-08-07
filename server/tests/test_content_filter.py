"""The Apple Guideline 1.2 content filter, and the false positives it must not create.

Guideline 1.2 asks for "a method for filtering objectionable material from being
posted". Sparrow had the report path, blocking and a zero-tolerance EULA clause
but no filter — and once the Acceptable Use Policy and Marketplace Terms began
asserting zero tolerance, the documents claimed a standard the code did not
enforce.

The risk with any wordlist is NOT under-blocking (a determined abuser routes
around it; the report path is what catches them). It is over-blocking: a false
positive silently stops a member selling a legitimate item, which is the failure
this codebase pays for most often. Hence the boundary-anchored matching, and
hence most of the tests below.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.lib.content_filter import find_blocked_term  # noqa: E402


def test_clean_listing_passes():
    assert find_blocked_term("Charizard Base Set, near mint", "Light edge wear") is None


@pytest.mark.parametrize("text", [
    "Scunthorpe United programme 1974",   # the canonical substring trap
    "Sussex county cricket badge",
    "Assassin's Creed collector's edition",
    "Classic Batman #1 reprint",
    "Analysis of the 1st print run",
    "Cocktail shaker, chrome",
    "Shitake mushroom enamel pin",
])
def test_innocent_listings_are_not_blocked(text):
    """Substring matching would reject every one of these. A member unable to
    list 'Scunthorpe United' would never guess why, and would conclude the app
    is broken."""
    assert find_blocked_term(text) is None, f"false positive on {text!r}"


def test_swearing_is_not_objectionable_content():
    """Filtering profanity would reject honest condition descriptions. Only
    slurs and hard-prohibited categories are listed."""
    assert find_blocked_term("Box is in shit condition, card is fine") is None
    assert find_blocked_term("Damn good copy") is None


@pytest.mark.parametrize("text", [
    "retard",
    "You RETARD",
    "some faggot thing",
    "tranny",
])
def test_slurs_are_blocked_case_insensitively(text):
    assert find_blocked_term(text) is not None


def test_it_checks_every_field_not_just_the_title():
    """A seller who puts a slur in the description rather than the title must
    not slip through — the description is shown on the listing page."""
    assert find_blocked_term("Clean title", "retard", None) == "retard"
    assert find_blocked_term("Clean title", None, "retard") == "retard"


def test_it_returns_the_term_so_the_seller_can_fix_it():
    """A generic refusal on a listing the seller believes is fine reads as the
    app being broken."""
    assert find_blocked_term("a retard thing") == "retard"


def test_none_and_empty_are_safe():
    assert find_blocked_term(None) is None
    assert find_blocked_term("") is None
    assert find_blocked_term(None, None, None) is None
