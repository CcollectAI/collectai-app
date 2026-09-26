"""Concerts are concerts, park tickets are not events (2026-09-26).

54% of the event feed was music labelled "Convention": the query tables
stamped every music keyword with kind 'convention'. The providers' own
classification now decides. And "Legoland Windsor - Daily Entry", once per
calendar day, filled the LEGO feed as conventions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.ticketmaster_events import _event_kind as tm_kind, _event_to_scraped as tm_map  # noqa: E402
from pipelines.seatgeek_events import _event_kind as sg_kind  # noqa: E402


def _tm(name, segment=None):
    ev = {"name": name, "dates": {"start": {"localDate": "2026-10-01"}}}
    if segment:
        ev["classifications"] = [{"segment": {"name": segment}}]
    return ev


def test_ticketmaster_music_segment_is_a_concert():
    assert tm_kind(_tm("LE SSERAFIM Tour", "Music"), "convention") == "concert"


def test_ticketmaster_non_music_keeps_the_query_default():
    assert tm_kind(_tm("Rhode Island Comic Con", "Arts & Theatre"), "convention") == "convention"
    assert tm_kind(_tm("Some Show"), "convention") == "convention"


def test_ticketmaster_daily_entry_is_not_an_event():
    assert tm_map(_tm("Legoland Windsor - Daily Entry"), "lego", "convention") is None


def test_a_conventions_own_multi_day_pass_is_kept():
    ev = tm_map(_tm("Rhode Island Comic Con 3 Day Vip Pass", "Miscellaneous"), "comic_books", "convention")
    assert ev is not None and ev.kind == "convention"


def test_seatgeek_concert_type_or_taxonomy():
    assert sg_kind({"type": "concert"}, "convention") == "concert"
    assert sg_kind({"type": "theater", "taxonomies": [{"name": "concert"}]}, "convention") == "concert"
    assert sg_kind({"type": "sports"}, "convention") == "convention"


def test_the_mapping_uses_the_classification():
    ev = tm_map(_tm("BTS World Tour", "Music"), "kpop_merch", "convention")
    assert ev is not None and ev.kind == "concert"
