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


class TestSameSourceDifferentVenue:
    """2026-10-14: store events share a template title across venues."""


    def _row(self, title, source, location, category="lorcana"):
        return {"title": title, "source": source, "location": location, "category_id": category}

    def test_same_template_title_at_two_stores_is_two_events(self):
        from pipelines.event_dedup import _is_duplicate_pair
        t = "Friday Evening Hyperia City Prerelease (Sealed)"
        a = self._row(t, "ravensburger_play", "Paradisecards TCG, Nieuwe Ebbingestraat 17, 9712 NC Groningen")
        b = self._row(t, "ravensburger_play", "Spielraum Bielefeld, Handwerkerstraße 7, 33617 Bielefeld, Germany")
        assert _is_duplicate_pair(a, b) is False

    def test_same_title_same_venue_same_source_is_still_a_duplicate(self):
        from pipelines.event_dedup import _is_duplicate_pair
        loc = "Paradisecards TCG, Nieuwe Ebbingestraat 17, 9712 NC Groningen"
        t = "Friday Evening Hyperia City Prerelease (Sealed)"
        assert _is_duplicate_pair(self._row(t, "ravensburger_play", loc), self._row(t, "ravensburger_play", loc)) is True

    def test_cross_vendor_rule_unchanged(self):
        from pipelines.event_dedup import _is_duplicate_pair
        a = self._row(TM_TITLE, "ticketmaster", "MetLife Stadium, East Rutherford, US", "kpop_merch")
        b = self._row(SG_TITLE, "seatgeek", "MetLife Stadium, East Rutherford, US", "kpop_merch")
        assert _is_duplicate_pair(a, b) is True
