"""Discogs: stored per observation, loud when it stores nothing, not heavy.

2026-09-27: 724 vinyl releases priced, 0 rows stored, run recorded `ok`. The
key `discogs:<release>` collided with the first row ever written, and
upsert_market_hits_batch is insert-if-absent across all partitions.
"""
from datetime import date

import pipelines.import_discogs as d
import workers.bake_orchestrator as bo


def test_listing_id_is_a_dated_snapshot():
    assert d.snapshot_listing_id(123, date(2026, 9, 27)) == "discogs:123:2026-09-27"


def test_two_days_are_two_rows_not_one():
    assert d.snapshot_listing_id(123, date(2026, 9, 27)) != d.snapshot_listing_id(123, date(2026, 10, 4))


def test_process_category_uses_the_snapshot_key(monkeypatch):
    monkeypatch.setattr(d, "_best_release_match", lambda c, t, cat: {"id": 55})
    monkeypatch.setattr(d, "_release_stats", lambda c, rid: {
        "lowest_price": 12.5, "title": "X", "url": "https://www.discogs.com/release/55", "image_url": None,
    })
    monkeypatch.setattr(d, "REQUEST_INTERVAL_S", 0)
    seen = []
    monkeypatch.setattr(d, "_upsert", lambda hits, stats: seen.extend(hits) or len(hits))
    d.process_category(None, "vinyl_records", [{"title": "X", "item_key": "k"}], False, d.IngestStats())
    assert len(seen) == 1
    assert seen[0].listing_id == d.snapshot_listing_id(55)


def _run(monkeypatch, upserted, dry_run=False):
    monkeypatch.setenv("DB_DSN", "postgres://x")
    monkeypatch.setattr(d, "TARGET_CATEGORIES", ["vinyl_records"])
    monkeypatch.setattr(d, "_get_stale_items_pg", lambda dsn, cat, lim: [{"title": "X", "item_key": "k"}])
    monkeypatch.setattr(d, "process_category", lambda *a, **k: {
        "category": "vinyl_records", "items_processed": 1, "releases_matched": 1,
        "with_listings": 724, "upserted": upserted,
    })
    return d.run_pipeline(dry_run=dry_run)


def test_priced_but_stored_nothing_is_NOT_ok(monkeypatch):
    assert _run(monkeypatch, upserted=0)["ok"] is False


def test_priced_and_stored_is_ok(monkeypatch):
    assert _run(monkeypatch, upserted=724)["ok"] is True


def test_dry_run_never_writes_and_is_ok(monkeypatch):
    assert _run(monkeypatch, upserted=0, dry_run=True)["ok"] is True


def test_discogs_does_not_hold_the_heavy_gate():
    # Measured <2 s of DB time per 1.5-2.25 h run; holding the gate parked
    # ingest behind it. See the comment in _HEAVY_WORKERS.
    assert "discogs_worker" not in bo._HEAVY_WORKERS
