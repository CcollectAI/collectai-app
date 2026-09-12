"""`coverage_zero_categories` must page for a source that DIED and not for one
that never existed.

WHY (2026-09-12): the check paged Telegram on every cycle with *"3 categories
have 0 hits in 7d. Likely adapter outage"* for `comic_books`, `dnd` and
`jewellery`. Measured on prod, all three had **zero hits ever** — no outage had
occurred, and the sentence naming one was a wrong diagnosis stated as fact. The
repeat is the damage: `docs/WATCHDOG.md` says twice that a daily siren is how a
channel stops being read, and its coverage canary already makes exactly this
split ("never any sold comps" is one aggregated finding, not 46 pages).

A check that has only ever produced one verdict has not been shown to
discriminate, so both verdicts are asserted here against fixture rows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from workers.sanity_probe_worker import classify_coverage_silence

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def test_never_seen_category_does_not_page():
    """The real 2026-09-12 case: three categories with no hit in retention."""
    rows = [
        {"category": "comic_books", "last_hit": None},
        {"category": "dnd", "last_hit": None},
        {"category": "jewellery", "last_hit": None},
    ]
    stopped, never = classify_coverage_silence(rows)
    assert stopped == []
    assert never == ["comic_books", "dnd", "jewellery"]


def test_a_source_that_died_still_pages():
    """The case the check exists for must survive the fix."""
    died_at = NOW - timedelta(days=9)
    rows = [{"category": "pokemon", "last_hit": died_at}]
    stopped, never = classify_coverage_silence(rows)
    assert stopped == [("pokemon", died_at)]
    assert never == []


def test_mixed_reports_each_in_its_own_bucket():
    """A real report will carry both, and they must not contaminate."""
    died_at = NOW - timedelta(days=30)
    rows = [
        {"category": "jewellery", "last_hit": None},
        {"category": "mtg", "last_hit": died_at},
        {"category": "dnd", "last_hit": None},
    ]
    stopped, never = classify_coverage_silence(rows)
    assert stopped == [("mtg", died_at)]
    assert never == ["jewellery", "dnd"]


def test_empty_input_is_silence_not_a_page():
    stopped, never = classify_coverage_silence([])
    assert stopped == []
    assert never == []
