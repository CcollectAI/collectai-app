"""Cross-vendor event dedup — the case Jaccard could not see.

Written 2026-07-27. Ticketmaster and SeatGeek both list the same concert;
SeatGeek writes the bare artist name, Ticketmaster the full billing. The
existing 0.70 Jaccard threshold scored that pair 0.14, so every such
concert was stored twice and both appeared in the feed.
"""
from __future__ import annotations

import pytest

from pipelines.event_dedup import (
    _SOURCE_RANK,
    _city_of,
    _token_containment,
    _token_overlap,
)

TM_TITLE = "BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD"
SG_TITLE = "BTS"


class TestWhyJaccardMissedIt:
    def test_jaccard_scores_the_real_pair_below_threshold(self):
        """Pinned so nobody 'simplifies' back to Jaccard alone."""
        assert _token_overlap(TM_TITLE, SG_TITLE) < 0.70

    def test_containment_catches_it(self):
        assert _token_containment(TM_TITLE, SG_TITLE) == 1.0

    @pytest.mark.parametrize("tm,sg", [
        ("BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD", "BTS"),
        ("BTS WORLD TOUR 'ARIRANG' IN FOXBOROUGH", "BTS"),
        ("Big Lick Comic Con Celebrity Guests", "Big Lick Comic Con"),
    ])
    def test_observed_production_pairs(self, tm, sg):
        assert _token_containment(tm, sg) >= 0.99


class TestContainmentDoesNotOvermatch:
    def test_unrelated_titles(self):
        assert _token_containment("Comic Con Omaha", "Anime Expo Chicago") < 0.99

    def test_empty(self):
        assert _token_containment("", "BTS") == 0.0
        assert _token_containment("BTS", "") == 0.0

    def test_ticket_tiers_are_a_containment_match_hence_the_guards(self):
        """"Day 1" vs "2-DAY VIP" of one convention DO contain each other.

        That is why containment is applied only ACROSS sources and within
        the same city — within a single vendor these are genuinely separate
        listings and must not be collapsed. Documented here rather than
        left as a surprise.
        """
        assert _token_containment(
            "Mid-Hudson Comic Con - Day 1", "Mid-Hudson Comic Con"
        ) >= 0.99


class TestVendorPrecedence:
    def test_ticketmaster_outranks_seatgeek(self):
        assert _SOURCE_RANK["ticketmaster"] < _SOURCE_RANK["seatgeek"]

    def test_unknown_sources_fall_back(self):
        assert _SOURCE_RANK.get("musicbrainz") is None


class TestCityExtraction:
    @pytest.mark.parametrize("loc,expected", [
        ("MetLife Stadium, East Rutherford, United States", "east rutherford"),
        ("Gillette Stadium, Foxborough, United States", "foxborough"),
        ("indigo at The O2, London, Great Britain", "london"),
    ])
    def test_city_is_the_middle_component(self, loc, expected):
        assert _city_of(loc) == expected

    def test_missing_or_malformed(self):
        assert _city_of(None) == ""
        assert _city_of("") == ""
        assert _city_of("SomewhereWithNoCommas") == ""
