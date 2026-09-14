"""Ticketmaster locations must read as a place, not as the API's raw parts.

WHY (2026-09-14): walked on Android, event rows read
"Epic Studios, Norwich , Great Britain" and
"St Georges Hall, Bradford , Bradford, Great Britain" — trailing whitespace in
Ticketmaster's venue/city names, and a city repeated after a venue name that
already ends with it. 8 upcoming prod rows, all source='ticketmaster'.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.ticketmaster_events import _compose_location  # noqa: E402


def test_trailing_whitespace_does_not_leave_a_space_before_the_comma():
    assert _compose_location("Epic Studios, Norwich ", "Norwich", "Great Britain") == (
        "Epic Studios, Norwich, Great Britain"
    )
    assert _compose_location("White Oak Music Hall - Upstairs ", "Houston", "United States Of America") == (
        "White Oak Music Hall - Upstairs, Houston, United States Of America"
    )


def test_city_already_in_the_venue_name_is_not_repeated():
    assert _compose_location("St Georges Hall, Bradford ", "Bradford", "Great Britain") == (
        "St Georges Hall, Bradford, Great Britain"
    )


def test_a_city_inside_the_venue_name_is_kept():
    # Measured against live Ticketmaster 2026-09-14: a suffix rule rewrote 15 of
    # 115 locations that were fine. Only an exact repeated SEGMENT is a repeat.
    assert _compose_location("O2 Academy Glasgow", "Glasgow", "Great Britain") == (
        "O2 Academy Glasgow, Glasgow, Great Britain"
    )
    assert _compose_location("Stratford", "Ford", "Great Britain") == "Stratford, Ford, Great Britain"


def test_ordinary_parts_join_unchanged():
    assert _compose_location("Madison Square Garden", "New York", "United States Of America") == (
        "Madison Square Garden, New York, United States Of America"
    )


def test_missing_and_blank_parts():
    assert _compose_location(None, "Paris", "France") == "Paris, France"
    assert _compose_location("  ", None, "") is None
    assert _compose_location(None, None, None) is None
