"""Events upsert: coordinates only when the source gave them (2026-10-15).

Sending latitude=NULL would overwrite what event_enrich geocoded (PostgREST
merge-duplicates updates every column in the payload), and a batch whose rows
disagree on keys is rejected whole (PGRST102). DATA_SCALING_PLAN §10.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.newsletter_scraper import EventUpserter, ScrapedEvent  # noqa: E402


def _ev(i, lat=None, lon=None):
    return ScrapedEvent(title=f"Prerelease {i}", kind="meetup", category_id="lorcana",
                        date="2026-10-16", time="19:00", location="Store, 1 Street, City, NL",
                        source_url=f"https://tcg.ravensburgerplay.com/events/{i}",
                        latitude=lat, longitude=lon)


def test_row_has_coordinates_only_when_the_source_gave_both():
    with_geo = EventUpserter._event_to_row(_ev(1, 52.1, 5.2), source="ravensburger_play")
    without = EventUpserter._event_to_row(_ev(2), source="ticketmaster")
    half = EventUpserter._event_to_row(_ev(3, 52.1, None), source="ravensburger_play")
    assert (with_geo["latitude"], with_geo["longitude"]) == (52.1, 5.2)
    assert "latitude" not in without and "longitude" not in without
    assert "latitude" not in half


def test_a_mixed_batch_is_posted_as_one_request_per_key_set():
    up = EventUpserter()
    client = MagicMock()
    client.post.return_value = MagicMock(status_code=201)
    up._client = client
    up._upsert_batch([_ev(1, 52.1, 5.2), _ev(2), _ev(3, 51.0, 4.0)],
                     conflict_key="source_url", source="ravensburger_play")
    posted = [call.kwargs["json"] for call in client.post.call_args_list]
    assert len(posted) == 2
    for batch in posted:
        assert len({frozenset(r) for r in batch}) == 1  # one key set per request
    assert sorted(len(b) for b in posted) == [1, 2]
