"""Ingest-time repair/rejection — pinned against the real production junk.

Written 2026-07-27. The display gate (test_event_quality_penalties.py)
stops junk reaching users; this stops it being STORED. Fixtures are the
verbatim titles/locations of all 14 `source='newsletter'` rows.
"""
from __future__ import annotations

import pytest

from app.lib.event_quality import clean_location, clean_title, reject_reason

FUTURE = "2026-12-01"


# (raw_title, raw_location) exactly as stored in prod.
PROD_JUNK = [
    ("Gimme your genius idea", "is HDCC?](https://www"),
    ("Site Navigation", "e Events"),
    ("Check out the latest gamescom news \U0001F525:", "ion](https://www"),
    ("Visit Usseguici sui social", "ional Sites & Searchricerc"),
    ("What is Gen Con?", "e your browser for more se"),
    ("Filter News Articles", "ic/media/pcenLogo"),
    ("Podcasts & More", "hering Logo](https://image"),
    ("We use Cookies", "est](https://stockx"),
    ("Attention!", "ions](https://www"),
]

REAL_TITLES = [
    "Legoland Windsor - Daily Entry",
    "BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD",
    "Everett AquaSox vs. Vancouver Canadians",
    "Mid-Hudson Comic Con - Day 1",
    "Camp Bestival 2026 - Backstage Camping",
    "Rare Candy Club Showdown #34 (PITCH BLACK LEGAL) (PTCG)",
    # Genuinely short real titles — this is why "too short" and "starts
    # lowercase" were measured and REJECTED as rejection signals.
    "BTS",
    "KUN",
]


@pytest.mark.parametrize("raw_title,raw_loc", PROD_JUNK)
def test_prod_junk_is_rejected_at_ingest(raw_title, raw_loc):
    title = clean_title(raw_title)
    assert reject_reason(title, FUTURE) is not None, (
        f"junk would still be stored: {raw_title!r} -> {title!r}"
    )


@pytest.mark.parametrize("title", REAL_TITLES)
def test_real_titles_survive(title):
    cleaned = clean_title(title)
    assert cleaned == title, f"clean_title mangled a real title: {title!r} -> {cleaned!r}"
    assert reject_reason(cleaned, FUTURE) is None, f"real event rejected: {title!r}"


class TestRepairBeforeReject:
    """A good name wearing markdown is recovered, not discarded."""

    def test_nike_markdown_title_is_unwrapped_into_a_real_event(self):
        raw = "[Nike Vaporposite Pro](https://sneakernews.com/2025/09/01/nike-vaporposite-pro)"
        assert clean_title(raw) == "Nike Vaporposite Pro"
        assert reject_reason(clean_title(raw), FUTURE) is None

    def test_leading_bracket_from_a_truncated_link_is_stripped(self):
        raw = "[ Disneyland Resort Welcomes One Billionth Guest"
        assert clean_title(raw) == "Disneyland Resort Welcomes One Billionth Guest"

    def test_dangling_separator_is_trimmed_not_rejected_when_name_survives(self):
        assert clean_title("Spielwarenmesse Nuremberg –") == "Spielwarenmesse Nuremberg"

    def test_spielwarenmesse_is_recovered_not_discarded(self):
        """Second row the repair pass turns back into a real event.

        Stored as "Spielwarenmesse –" with the venue
        "ion partner](https://www". The venue is debris and is dropped,
        but Spielwarenmesse IS the Nuremberg Toy Fair (see
        docs/EVENTS_API_COVERAGE.md) — rejecting it would discard a real
        event to punish a trailing dash.
        """
        title = clean_title("Spielwarenmesse –")
        assert title == "Spielwarenmesse"
        assert reject_reason(title, FUTURE) is None
        assert clean_location("ion partner](https://www") is None

    def test_whitespace_is_collapsed(self):
        assert clean_title("  Comic   Con\n\tOmaha ") == "Comic Con Omaha"

    def test_empty_and_none(self):
        assert clean_title(None) == ""
        assert clean_title("   ") == ""
        assert reject_reason("", FUTURE) == "title_too_short"


class TestLocationCleaning:
    """Debris becomes NULL; the event itself survives."""

    @pytest.mark.parametrize("raw_title,raw_loc", PROD_JUNK)
    def test_all_prod_junk_locations_are_dropped(self, raw_title, raw_loc):
        assert clean_location(raw_loc) is None

    @pytest.mark.parametrize("loc", [
        "MetLife Stadium, East Rutherford, United States",
        "Legoland Windsor, Windsor, Great Britain",
        "indigo at The O2, London, Great Britain",  # real, stylised lowercase
    ])
    def test_real_venues_survive(self, loc):
        assert clean_location(loc) == loc

    @pytest.mark.parametrize("loc", ["Online", "TBA", "Virtual"])
    def test_venueless_but_valid_survives(self, loc):
        assert clean_location(loc) == loc

    def test_none_and_empty(self):
        assert clean_location(None) is None
        assert clean_location("  ") is None


class TestRejectReasons:
    def test_no_date_is_rejected(self):
        assert reject_reason("Comic Con Omaha", None) == "no_date"
        assert reject_reason("Comic Con Omaha", "") == "no_date"

    def test_question_titles(self):
        assert reject_reason("What is Gen Con?", FUTURE) == "question_title"

    def test_boilerplate_is_case_and_punctuation_insensitive(self):
        assert reject_reason("SITE NAVIGATION", FUTURE) == "boilerplate_title"
        assert reject_reason("Attention!", FUTURE) == "boilerplate_title"

    def test_raw_markup_surviving_cleaning_is_rejected(self):
        assert reject_reason("http://example.com/thing", FUTURE) == "markup_in_title"
