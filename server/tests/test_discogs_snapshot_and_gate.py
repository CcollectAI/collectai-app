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


# ── Remembered misses (2026-09-27) ──────────────────────────────────────────
# anime_ost_vinyl: 1,103 probed, 376 matched, 293 priced — the other ~810 were
# re-searched every day because a miss left no row.

def _probe(monkeypatch, match, stats=None):
    monkeypatch.setattr(d, "_best_release_match", lambda c, t, cat: match)
    monkeypatch.setattr(d, "_release_stats", lambda c, rid: stats)
    monkeypatch.setattr(d, "REQUEST_INTERVAL_S", 0)
    monkeypatch.setattr(d, "_upsert", lambda hits, st: len(hits))
    recorded = []
    monkeypatch.setattr(d, "_record_misses", lambda m: recorded.extend(m))
    r = d.process_category(None, "anime_ost_vinyl", [{"title": "X", "item_key": "k"}], False, d.IngestStats())
    return r, recorded


def test_no_match_is_remembered(monkeypatch):
    r, rec = _probe(monkeypatch, None)
    assert rec == [("anime_ost_vinyl:k", "no_match")]
    assert r["misses"] == 1


def test_matched_but_nothing_for_sale_is_remembered_as_no_price(monkeypatch):
    r, rec = _probe(monkeypatch, {"id": 9}, {"lowest_price": None, "title": "X", "url": "u", "image_url": None})
    assert rec == [("anime_ost_vinyl:k", "no_price")]


def test_a_FAILED_search_is_not_a_miss(monkeypatch):
    # A 429 or timeout must not hide the item for 30 days.
    r, rec = _probe(monkeypatch, d._FAILED)
    assert rec == []


def test_a_FAILED_release_fetch_is_not_a_miss(monkeypatch):
    r, rec = _probe(monkeypatch, {"id": 9}, d._FAILED)
    assert rec == []


def test_a_failed_http_call_returns_FAILED_not_None(monkeypatch):
    monkeypatch.setattr(d, "_get", lambda *a, **k: None)
    assert d._best_release_match(None, "X", "vinyl_records") is d._FAILED
    assert d._release_stats(None, 1) is d._FAILED


def test_an_empty_search_answer_is_None(monkeypatch):
    monkeypatch.setattr(d, "_get", lambda *a, **k: {"results": []})
    assert d._best_release_match(None, "X", "vinyl_records") is None


def test_the_stale_query_skips_remembered_misses():
    import inspect
    src = inspect.getsource(d._get_stale_items_pg)
    # The FROM clause, not the name: the comment above the clause also names
    # the table, and a check on the bare name survived a typo in the query.
    assert "FROM public.discogs_probe_misses m" in src
    assert "INTERVAL '30 days'" in src and "INTERVAL '14 days'" in src
    # The recheck windows in SQL must match the documented constant.
    assert d.MISS_RECHECK_DAYS == {"no_match": 30, "no_price": 14}


def test_there_is_one_copy_of_the_stale_query():
    import pathlib
    src = pathlib.Path(d.__file__).read_text()
    assert src.count("mh.provider = 'discogs_listing'") == 1
