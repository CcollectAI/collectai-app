"""`_compose_starts_at` must never let a bad TIME destroy a good DATE.

Regression test for the 2026-09-01 finding: Ticketmaster's `dates.start.localTime`
is `HH:MM:SS`, the composer parsed with `%H:%M`, and the resulting ValueError was
swallowed into `return None`. 509 of 588 Ticketmaster rows (86.6%) landed with
`starts_at IS NULL` while Postgres happily stored the very same value in
`events.time`.

The date is the field that decides whether an event is real; the time only
refines it. So the invariant under test is asymmetric on purpose:

    date parseable  -> starts_at is NOT NULL, whatever the time looks like
    date unparseable -> starts_at is None
"""
from pipelines.newsletter_scraper import _compose_starts_at


def test_seconds_precision_time_is_parsed():
    """Ticketmaster's real format. This is the case that was silently dropped."""
    assert _compose_starts_at("2026-11-13", "19:30:00") == "2026-11-13T19:30:00+00:00"


def test_minute_precision_time_still_parsed():
    """SeatGeek/limitless format must keep working."""
    assert _compose_starts_at("2026-11-13", "19:30") == "2026-11-13T19:30:00+00:00"


def test_absent_time_falls_back_to_midnight():
    assert _compose_starts_at("2026-11-13", None) == "2026-11-13T00:00:00+00:00"


def test_unparseable_time_keeps_the_date():
    """The whole point: a junk time degrades precision, it does not delete the row.

    Before the fix every one of these returned None and the event lost its
    timestamp entirely.
    """
    for junk in ("7pm", "19.30", "doors at 8", "", "25:99:99"):
        got = _compose_starts_at("2026-11-13", junk)
        assert got == "2026-11-13T00:00:00+00:00", f"time={junk!r} destroyed the date: {got!r}"


def test_unparseable_date_is_still_none():
    """A missing or malformed date genuinely has nothing to compose."""
    assert _compose_starts_at(None, "19:30:00") is None
    assert _compose_starts_at("", "19:30:00") is None
    assert _compose_starts_at("13-11-2026", "19:30:00") is None
    assert _compose_starts_at("not a date", None) is None
