"""`coverage_zero_categories` must page for a source that DIED, and not for a
category that never had one or that nobody has asked yet.

WHY (2026-09-12): the check paged Telegram on every cycle with *"3 categories
have 0 hits in 7d. Likely adapter outage"* for `comic_books`, `dnd` and
`jewellery`. Measured on prod, all three had **zero hits ever** — no outage had
occurred, and the sentence naming one was a wrong diagnosis stated as fact. The
repeat is the damage: `docs/WATCHDOG.md` says twice that a daily siren is how a
channel stops being read, and its coverage canary already makes exactly this
split ("never any sold comps" is one aggregated finding, not 46 pages).

WHY (2026-09-13): the split above still paged hourly for `one_piece_tcg` and
`digimon` ("last 2026-09-06"). Nothing had died. `marketplace_scrape_worker`
retries the least-recently-attempted item across ~87k catalogue rows at ~1,500
a day — a ~58-day rotation — and both categories had simply had their turn.
eBay wrote 15.5k hits that same day. A check on a scheduled writer must know
its schedule (`docs/WATCHDOG.md` "Checks must know the schedule they police"),
and the worker already records it: `category_items.last_scrape_attempt_at`.

The first draft of that fix paged on ANY attempt after the last hit, and the
real prod rows showed it wrong before it shipped: sportscards, funko and
anime_ost_vinyl had 1-2 stray empty attempts each, while healthy categories
return nothing on up to ~70% of items. Hence a minimum.

A check that has only ever produced one verdict has not been shown to
discriminate, so every verdict is asserted here — the counts are real prod rows
from 2026-09-13 unless a test says otherwise.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from workers.sanity_probe_worker import (
    COVERAGE_MIN_EMPTY_ATTEMPTS,
    classify_coverage_silence,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _row(category, last_hit, asked_since=0, visited_at_last_hit=0):
    return {
        "category": category,
        "last_hit": last_hit,
        "asked_since": asked_since,
        "visited_at_last_hit": visited_at_last_hit,
    }


def test_never_seen_category_does_not_page():
    """The real 2026-09-12 case: three categories with no hit in retention."""
    rows = [_row("jewellery", None), _row("dnd", None), _row("comic_books", None)]
    assert classify_coverage_silence(rows) == ([], [], ["jewellery", "dnd", "comic_books"])


def test_category_the_scraper_has_not_revisited_does_not_page():
    """The real 2026-09-13 page: 5 items stamped by the visit that wrote the
    last hit, 0 asked since."""
    last_hit = datetime(2026, 9, 6, 9, 34, 17, tzinfo=timezone.utc)
    rows = [_row("one_piece_tcg", last_hit, asked_since=0, visited_at_last_hit=5)]
    assert classify_coverage_silence(rows) == ([], [("one_piece_tcg", last_hit)], [])


def test_a_few_stray_empty_attempts_do_not_page():
    """The real rows that broke the first draft: sportscards had 2 empty
    attempts a day after its visit, funko 1. Neither is a dead source."""
    sc = datetime(2026, 9, 9, 10, 15, tzinfo=timezone.utc)
    fk = datetime(2026, 9, 11, 7, 57, tzinfo=timezone.utc)
    rows = [
        _row("sportscards", sc, asked_since=2, visited_at_last_hit=1),
        _row("funko", fk, asked_since=1, visited_at_last_hit=3),
    ]
    stopped, not_asked, _ = classify_coverage_silence(rows)
    assert stopped == []
    assert not_asked == [("sportscards", sc), ("funko", fk)]


def test_asked_again_many_times_and_got_nothing_still_pages():
    """The scraper came back, asked a full visit's worth, got nothing: that IS
    a source that died, and it is what the check exists for."""
    last_hit = NOW - timedelta(days=9)
    rows = [_row("warhammer", last_hit, asked_since=40, visited_at_last_hit=3)]
    assert classify_coverage_silence(rows) == ([("warhammer", last_hit)], [], [])


def test_a_feed_that_died_still_pages():
    """lorcana is fed by lorcast (source NULL). If lorcast dies, no scraper
    visit wrote the last hit — "nobody asked" would be false for the feed."""
    last_hit = NOW - timedelta(days=8)
    rows = [_row("lorcana", last_hit, asked_since=0, visited_at_last_hit=0)]
    assert classify_coverage_silence(rows) == ([("lorcana", last_hit)], [], [])


def test_a_category_excluded_from_the_rotation_is_never_not_asked():
    """"Nobody asked" is only benign for a category somebody WILL ask. A skip
    list holding lorcana/digimon/one_piece_tcg kept 24,404 catalogue items
    dark until 2026-08-06; that silence must page, visit or not."""
    last_hit = NOW - timedelta(days=9)
    rows = [_row("one_piece_tcg", last_hit, asked_since=0, visited_at_last_hit=5)]
    excluded = frozenset({"one_piece_tcg"})
    assert classify_coverage_silence(rows, excluded) == ([("one_piece_tcg", last_hit)], [], [])


def test_the_live_skip_list_is_what_the_check_reads():
    """The exclusion set is the scheduler's own constant, not a copy of it."""
    import inspect

    from workers import sanity_probe_worker
    from workers.marketplace_scrape_scheduler import SKIP_CATEGORIES

    src = inspect.getsource(sanity_probe_worker._check_coverage_zero)
    assert "from workers.marketplace_scrape_scheduler import SKIP_CATEGORIES" in src
    assert "classify_coverage_silence(rows, SKIP_CATEGORIES)" in src
    assert SKIP_CATEGORIES  # an empty import would make the rule a no-op


def test_threshold_boundary():
    last_hit = NOW - timedelta(days=10)
    n = COVERAGE_MIN_EMPTY_ATTEMPTS
    below = [_row("a", last_hit, asked_since=n - 1, visited_at_last_hit=1)]
    at = [_row("b", last_hit, asked_since=n, visited_at_last_hit=1)]
    assert classify_coverage_silence(below)[0] == []
    assert classify_coverage_silence(at)[0] == [("b", last_hit)]


def test_threshold_is_not_trivially_small():
    """The number is derived from a measured ~70% per-item empty rate; a value
    that small categories cross by chance would bring the hourly page back."""
    assert 0.70 ** COVERAGE_MIN_EMPTY_ATTEMPTS < 0.001


def test_mixed_reports_each_in_its_own_bucket():
    """A real report will carry all three, and they must not contaminate."""
    died = NOW - timedelta(days=30)
    visited = NOW - timedelta(days=8)
    rows = [
        _row("jewellery", None),
        _row("mtg", died, asked_since=0, visited_at_last_hit=0),
        _row("digimon", visited, asked_since=0, visited_at_last_hit=2),
        _row("dnd", None),
    ]
    assert classify_coverage_silence(rows) == (
        [("mtg", died)],
        [("digimon", visited)],
        ["jewellery", "dnd"],
    )


def test_empty_input_is_silence_not_a_page():
    assert classify_coverage_silence([]) == ([], [], [])
