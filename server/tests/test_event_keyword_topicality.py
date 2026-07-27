"""Search keyword must describe the EVENT, not its venue.

Written 2026-07-27. `QUERIES` in ticketmaster_events.py / seatgeek_events.py
maps a search keyword to a category_id, and the mapping was trusted
unconditionally — so anything the provider's keyword search matched for any
reason inherited that category.

Observed in production: 5+ "Everett AquaSox vs. <team>" minor-league
baseball games filed under `funko`, because they are played at **Funko
Field** in Everett WA, a ballpark named after the company's nearby HQ.
"""
from __future__ import annotations

import pytest

from pipelines.seatgeek_events import _keyword_matches_event as sg_matches
from pipelines.ticketmaster_events import _keyword_matches_event as tm_matches


def tm_event(name: str, venue: str = "", attractions=(), classifications=()) -> dict:
    return {
        "name": name,
        "_embedded": {
            "venues": [{"name": venue}] if venue else [],
            "attractions": [{"name": a} for a in attractions],
        },
        "classifications": [
            {"segment": {"name": c}} for c in classifications
        ],
    }


class TestTicketmaster:
    def test_the_funko_field_bug(self):
        """The exact production shape that caused this."""
        ev = tm_event(
            "Everett AquaSox vs. Vancouver Canadians",
            venue="Funko Field",
            classifications=("Sports",),
        )
        assert tm_matches(ev, "funko") is False

    def test_a_real_funko_event_still_matches(self):
        ev = tm_event("Funko Fundays 2026", venue="Anaheim Convention Center")
        assert tm_matches(ev, "funko") is True

    def test_match_via_attraction_not_just_name(self):
        ev = tm_event("World Tour 2026", venue="MetLife Stadium", attractions=("BTS",))
        assert tm_matches(ev, "bts") is True

    @pytest.mark.parametrize("name,keyword", [
        ("BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD", "bts"),
        ("Mid-Hudson Comic Con - Day 1", "comic con"),
        ("Legoland Windsor - Daily Entry", "lego"),
        ("Camp Bestival 2026 - Backstage Camping", "camp bestival"),
    ])
    def test_real_production_events_survive(self, name, keyword):
        assert tm_matches(tm_event(name), keyword) is True

    @pytest.mark.parametrize("name,keyword", [
        ("Yugioh Regional Championship", "yu-gi-oh"),
        ("KPOP Night Live", "k-pop"),
        ("Magic: The Gathering Grand Prix", "magic the gathering"),
    ])
    def test_punctuation_and_case_are_normalised(self, name, keyword):
        assert tm_matches(tm_event(name), keyword) is True

    def test_venue_alone_never_qualifies(self):
        ev = tm_event("Some Unrelated Concert", venue="Lego Arena")
        assert tm_matches(ev, "lego") is False

    def test_missing_fields_do_not_raise(self):
        assert tm_matches({}, "funko") is False
        assert tm_matches({"name": None}, "funko") is False


class TestSeatGeek:
    def sg_event(self, title: str, venue: str = "", performers=()) -> dict:
        return {
            "title": title,
            "venue": {"name": venue},
            "performers": [{"name": p} for p in performers],
        }

    def test_venue_does_not_qualify(self):
        ev = self.sg_event("Everett AquaSox vs. Eugene Emeralds", venue="Funko Field")
        assert sg_matches(ev, "funko") is False

    def test_performer_qualifies(self):
        ev = self.sg_event("World Tour", venue="Gillette Stadium", performers=("BTS",))
        assert sg_matches(ev, "bts") is True

    def test_title_qualifies(self):
        assert sg_matches(self.sg_event("Bell County Comic Con - Belton"), "comic con") is True

    def test_missing_fields_do_not_raise(self):
        assert sg_matches({}, "funko") is False
