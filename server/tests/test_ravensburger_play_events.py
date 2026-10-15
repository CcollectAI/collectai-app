"""Ravensburger Play → events mapping (2026-10-14). No network."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.ravensburger_play_events import is_special, to_scraped_event  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def _ev(**kw):
    base = {
        "id": 871412, "name": "Friday Evening Hyperia City Prerelease (Sealed)", "game": 1,
        "start_datetime": "2026-10-16T16:00:00+00:00", "timezone": "Europe/Amsterdam",
        "event_status": "SCHEDULED", "is_test_event": False, "event_is_online": False,
        "store": {"name": "Paradisecards TCG"}, "full_address": "Nieuwe Ebbingestraat 17,\n9712 NC Groningen",
        "gameplay_format": {"name": "Sealed"}, "cost_in_cents": 3000, "currency": "EUR", "capacity": 32,
    }
    base.update(kw)
    return base


def test_prerelease_maps_to_a_lorcana_event_in_store_local_time():
    e = to_scraped_event(_ev(), now=NOW)
    assert e is not None
    assert e.category_id == "lorcana"
    assert (e.date, e.time) == ("2026-10-16", "18:00")  # 16:00Z = 18:00 CEST
    assert e.location == "Paradisecards TCG, Nieuwe Ebbingestraat 17, 9712 NC Groningen"
    assert e.source_url == "https://tcg.ravensburgerplay.com/events/871412"
    assert "Entry 30.00 EUR" in e.description


def test_weekly_play_is_not_an_event():
    assert to_scraped_event(_ev(name="Thursday Evening Weekly Play (Constructed)"), now=NOW) is None


def test_headlining_event_kept_whatever_its_name():
    assert is_special(_ev(name="Big Saturday", is_headlining_event=True))


def test_past_test_online_cancelled_and_other_games_are_dropped():
    assert to_scraped_event(_ev(start_datetime="2026-10-01T16:00:00+00:00"), now=NOW) is None
    assert to_scraped_event(_ev(is_test_event=True), now=NOW) is None
    assert to_scraped_event(_ev(event_is_online=True), now=NOW) is None
    assert to_scraped_event(_ev(event_status="CANCELED"), now=NOW) is None
    assert to_scraped_event(_ev(game=3), now=NOW) is None  # Riftbound
