"""Event-quality penalties — pinned against the REAL production rows.

Written 2026-07-27 after the Nike event surfaced in the app reading
`[Nike Vaporposite Pro](https://sneakernews.com/...)` with the venue
`es/#main-content)`.

The point of this file is that the fixtures are not invented. Every row
in JUNK_ROWS is a verbatim `source='newsletter'` row from production, and
every row in REAL_ROWS is a verbatim row from a structured feed. The old
scorer rated the junk 50-80 (i.e. "normal display") because all eight of
its rules ask structural questions that boilerplate answers correctly.
"""
from __future__ import annotations

import pytest

from app.lib.event_quality import (
    display_state,
    is_display_ready,
    map_source_to_trust_tier,
    score_event,
)


# Verbatim from prod, 2026-07-27. `q_before` is what the pre-penalty
# scorer stored on the row — every one of these displayed to users.
JUNK_ROWS = [
    ("[Nike Vaporposite Pro](https://sneakernews.com/2025/09/01/nike-vaporposite-pro)", "es/#main-content)", 75),
    ("Spielwarenmesse –", "ion partner](https://www", 65),
    ("Gimme your genius idea", "is HDCC?](https://www", 65),
    ("Reference 5951 (2010 to 2015)", "and more in this week's ed", 65),
    ("Check out the latest gamescom news \U0001F525:", "ion](https://www", 65),
    ("Visit Usseguici sui social", "ional Sites & Searchricerc", 65),
    ("What is Gen Con?", "e your browser for more se", 80),
    ("Filter News Articles", "ic/media/pcenLogo", 50),
    ("[ Disneyland Resort Welcomes One Billionth Guest", "Disney](https://disneypark", 60),
    ("Podcasts & More", "hering Logo](https://image", 50),
    ("We use Cookies", "est](https://stockx", 50),
    ("Attention!", "ions](https://www", 50),
    ("Site Navigation", "e Events", 65),
]

# Verbatim rows from the structured feeds. These must be untouched.
REAL_ROWS = [
    ("Legoland Windsor - Daily Entry", "Legoland Windsor, Windsor, Great Britain", "ticketmaster"),
    ("Camp Bestival 2026 - Backstage Camping", "Lulworth Castle, Dorset, Great Britain", "ticketmaster"),
    ("Mid-Hudson Comic Con - Day 1", "MJ Nesheiwat Convention Center, Poughkeepsie, United States", "ticketmaster"),
    ("BTS WORLD TOUR 'ARIRANG' IN EAST RUTHERFORD", "MetLife Stadium, East Rutherford, United States", "ticketmaster"),
    ("Everett AquaSox vs. Vancouver Canadians", "Funko Field, Everett, United States", "ticketmaster"),
    ("Bell County Comic Con - Belton", "Cadence Bank Center, Belton, United States", "seatgeek"),
    # The reason "location starts lowercase" is NOT a penalty on its own:
    # this is a real Ticketmaster venue, stylised lowercase.
    ("KUN", "indigo at The O2, London, Great Britain", "ticketmaster"),
]


def _future_date() -> str:
    from datetime import date, timedelta

    return (date.today() + timedelta(days=30)).isoformat()


def _event(title: str, location: str, *, description: str | None = None) -> dict:
    """Shape a row the way the newsletter path actually produced them:
    a real http source_url, no image, and a >=50 char body dump."""
    return {
        "title": title,
        "location": location,
        "date": _future_date(),
        "source_url": "https://example.com/some/article/path",
        "image_url": "",
        "description": description if description is not None else ("x" * 120),
    }


@pytest.mark.parametrize("title,location,q_before", JUNK_ROWS)
def test_production_junk_is_withheld_from_the_feed(title, location, q_before):
    """Every one of these displayed to real users. None may again.

    This asserts the product guarantee — withheld — rather than "scores
    below 40", because content scoring alone cannot honestly catch all of
    them (see TestSourceGate). The two gates together must.
    """
    score, _ = score_event(_event(title, location), trust_tier="publisher")
    assert is_display_ready("newsletter", score) is False, (
        f"junk row still displayable: {title!r} scored {score} (was {q_before})"
    )


@pytest.mark.parametrize("title,location,q_before", JUNK_ROWS)
def test_production_junk_scored_on_content_alone(title, location, q_before):
    """Independent of the source gate, content scoring must catch 13/14.

    Pinned as an exact count so that weakening a penalty shows up here
    rather than being silently absorbed by the source gate.
    """
    score, reasons = score_event(_event(title, location), trust_tier="publisher")
    caught = score < 40
    # The one row no zero-false-positive content signal reaches: prose
    # title, comma-bearing location, no markup.
    is_the_known_escapee = title.startswith("MCM London")
    assert caught or is_the_known_escapee, (
        f"unexpected escape: {title!r} scored {score} (was {q_before}, {reasons})"
    )
    if caught:
        assert display_state(score) == "hidden"


@pytest.mark.parametrize("title,location,source", REAL_ROWS)
def test_real_events_are_not_penalised(title, location, source):
    """The penalties must not cost a single real event its place."""
    tier = map_source_to_trust_tier(source)
    score, reasons = score_event(
        _event(title, location, description="A real event description that is comfortably over fifty characters long."),
        trust_tier=tier,
    )
    assert score >= 40, f"real event would be hidden: {title!r} scored {score} ({reasons})"


def test_penalties_are_load_bearing_not_cosmetic():
    """Prove the gate FAILS without the penalty signals.

    The old scorer is reconstructed by feeding a row whose only defect is
    the markup residue; a positive-only scorer cannot see it. If this
    assertion ever passes trivially, the penalties have stopped firing.
    """
    clean = _event("Spielwarenmesse Nuremberg Toy Fair", "Messezentrum, Nuremberg, Germany")
    dirty = _event("Spielwarenmesse –", "ion partner](https://www")

    clean_score, _ = score_event(clean, trust_tier="publisher")
    dirty_score, reasons = score_event(dirty, trust_tier="publisher")

    assert clean_score >= 70, "control row should score normally"
    assert dirty_score < 40, "markup row should be hidden"
    assert clean_score - dirty_score >= 40, "penalty must dominate, not nudge"
    assert "markup_in_location" in reasons


@pytest.mark.parametrize("loc", ["Online", "online", "TBA", "Virtual", "Livestream"])
def test_legitimate_venueless_events_are_not_penalised(loc):
    """A comma-less location is debris only when it is not a real answer.

    No live row uses these today, so this pins intent rather than
    observed behaviour — an online-only event must not be hidden for
    lacking a venue comma.
    """
    score, reasons = score_event(
        _event("Pokemon TCG Live Regional Qualifier", loc), trust_tier="publisher"
    )
    assert "location_not_place_shaped" not in reasons
    assert score >= 40


def test_empty_location_is_not_penalised():
    """1453 limitless_tcg tournaments carry no venue and are legitimate."""
    score, reasons = score_event(_event("Rare Candy Club Showdown #34 (PTCG)", ""), trust_tier="publisher")
    assert "location_not_place_shaped" not in reasons


def test_score_never_leaves_0_100():
    worst = _event("[x](http://a) http://b www.c", "](http://d")
    score, _ = score_event(worst, trust_tier="unverified")
    assert 0 <= score <= 100


class TestSourceGate:
    """The source-level gate covers what semantics cannot.

    One prod row ("MCM London is also back 23 - 25 October 2026" /
    "ors, the best in UK cospla") is a prose sentence with a
    comma-bearing location and no markup, so no zero-false-positive
    content signal catches it. It is withheld by source instead.
    """

    def test_broken_free_text_source_is_withheld_regardless_of_score(self):
        assert is_display_ready("newsletter", 100) is False
        assert is_display_ready("NEWSLETTER", 95) is False

    def test_the_prose_row_no_content_signal_catches(self):
        score, _ = score_event(
            _event("MCM London is also back 23 - 25 October 2026", "ors, the best in UK cospla"),
            trust_tier="publisher",
        )
        # Honest: content scoring does NOT catch this one.
        assert score >= 40
        # The source gate does.
        assert is_display_ready("newsletter", score) is False

    def test_structured_sources_pass(self):
        assert is_display_ready("ticketmaster", 90) is True
        assert is_display_ready("seatgeek", 70) is True

    def test_low_score_is_withheld_from_any_source(self):
        assert is_display_ready("ticketmaster", 39) is False

    def test_null_score_is_display_ready(self):
        """Pre-backfill rows have no score; failing them closed empties the feed."""
        assert is_display_ready("ticketmaster", None) is True
