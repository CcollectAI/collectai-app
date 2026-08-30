"""The category_items writer contract, as PostgREST and Postgres enforce it.

Written from the 2026-08-28 nightly-ingest run (GitHub Actions run 33181755459),
which logged **107 failed catalog batches** and still reported `success` --
`upsert_catalog` logs the HTTP error and continues, so up to ~21k catalogue rows
were dropped silently. Three distinct rejections, all reproduced here:

  15x  500 {"code":"21000","message":"ON CONFLICT DO UPDATE command cannot
           affect row a second time"}
  42x  400 {"code":"PGRST102","message":"All object keys must match"}
  50x  httpx "Cannot send a request, as the client has been closed."

`FakePostgrest` below encodes the SERVER's rules, not the current shape of our
code, so it stays honest if the writer is rewritten.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines import import_common
from pipelines.import_common import CatalogItem, SupabaseIngest


class FakeResp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class FakeServer:
    """The durable half — survives a client being closed and rebuilt."""

    def __init__(self):
        self.accepted: list[dict] = []
        self.rejections: list[str] = []


class FakePostgrest:
    """Simulates the two rejections PostgREST/Postgres actually returned."""

    def __init__(self, server: "FakeServer"):
        self.server = server
        self.is_closed = False

    def close(self):
        self.is_closed = True

    def post(self, url, headers=None, json=None, timeout=None):
        if self.is_closed:
            raise RuntimeError("Cannot send a request, as the client has been closed.")
        batch = json or []

        # PostgREST bulk insert requires every object in the array to carry the
        # IDENTICAL key set -- it builds one INSERT with one column list.
        if len({frozenset(r.keys()) for r in batch}) > 1:
            self.server.rejections.append("PGRST102")
            return FakeResp(400, '{"code":"PGRST102","message":"All object keys must match"}')

        # Postgres aborts the WHOLE statement if one ON CONFLICT target is hit
        # twice -- the other 199 rows in the batch are lost with it.
        seen = set()
        for r in batch:
            key = (r.get("category"), r.get("item_key"))
            if key in seen:
                self.server.rejections.append("21000")
                return FakeResp(500, '{"code":"21000","message":"ON CONFLICT DO UPDATE '
                                     'command cannot affect row a second time"}')
            seen.add(key)

        self.server.accepted.extend(batch)
        return FakeResp(201, "")


@pytest.fixture
def ingest(monkeypatch):
    """Mirrors the REAL get_http_client / close_http_client contract.

    get_http_client() rebuilds when the shared client is missing or closed, so
    the stub must too -- otherwise the test asserts against a stub weaker than
    production and proves nothing.
    """
    server = FakeServer()
    monkeypatch.setattr(import_common, "_shared_http_client", None, raising=False)

    def fake_get_http_client():
        cur = import_common._shared_http_client
        if cur is None or cur.is_closed:
            import_common._shared_http_client = FakePostgrest(server)
        return import_common._shared_http_client

    monkeypatch.setattr(import_common, "get_http_client", fake_get_http_client)
    ing = SupabaseIngest(batch_size=200)
    ing.enabled = True
    return ing, server


def _item(key, **kw):
    kw.setdefault("title", f"Card {key}")
    return CatalogItem(category="pokemon", item_key=key, **kw)


# ---------------------------------------------------------------------------
# 42 of 107: PGRST102 "All object keys must match"
# ---------------------------------------------------------------------------

def test_rows_with_and_without_optional_columns_all_land(ingest):
    """to_row() adds image_url/barcode/attributes_json CONDITIONALLY.

    A real catalogue page mixes rows that have an image with rows that do not,
    so a single batch carries two different key sets and PostgREST rejects the
    whole thing. All rows must still be written.
    """
    ing, fake = ingest
    items = [
        _item("charizard-holo", image_url="https://img/1.png"),
        _item("blastoise-holo"),                                  # no image
        _item("venusaur-holo", barcode="12345"),                  # different extra
    ]
    written = ing.upsert_catalog(items)

    assert fake.rejections == [], f"server rejected: {fake.rejections}"
    assert written == 3
    assert {r["item_key"] for r in fake.accepted} == {
        "charizard-holo", "blastoise-holo", "venusaur-holo"}


def test_an_absent_optional_column_is_never_sent_as_null(ingest):
    """Padding the key set with None would be a DATA-LOSS fix, not a fix.

    The upsert is Prefer: resolution=merge-duplicates, so a column present in
    the payload is overwritten and a column absent from it is left alone.
    Sending image_url=None for a row that simply has no image would blank an
    image the catalogue already holds.
    """
    ing, fake = ingest
    ing.upsert_catalog([
        _item("has-image", image_url="https://img/1.png"),
        _item("no-image"),
    ])
    no_image = [r for r in fake.accepted if r["item_key"] == "no-image"][0]
    assert "image_url" not in no_image or no_image["image_url"], \
        "row without an image must omit image_url, not send NULL"


# ---------------------------------------------------------------------------
# 15 of 107: 21000 within-batch duplicate
# ---------------------------------------------------------------------------

def test_within_batch_duplicates_do_not_abort_the_batch(ingest):
    """Pipelines legitimately repeat a key (pagination overlap, a card in two
    sets). One repeat must not take the other 199 rows down with it."""
    ing, fake = ingest
    written = ing.upsert_catalog([
        _item("pikachu", title="Pikachu"),
        _item("raichu"),
        _item("pikachu", title="Pikachu (reprint)"),   # same conflict target
    ])
    assert fake.rejections == [], f"server rejected: {fake.rejections}"
    assert written == 2
    assert {r["item_key"] for r in fake.accepted} == {"pikachu", "raichu"}


# ---------------------------------------------------------------------------
# 50 of 107: the shared client is closed underneath a still-running pipeline
# ---------------------------------------------------------------------------

def test_a_sibling_pipeline_closing_the_shared_client_does_not_strand_writes(ingest):
    """import_all runs pipelines in a ThreadPoolExecutor, and several of them
    (import_sneakers.py:3380, :3402 and friends) call the MODULE-GLOBAL
    close_http_client() when they individually finish. That closes the client
    every other thread is still writing through. On 2026-08-28 the pipelines
    that finished last -- Comic Books, Plush, Vintage Toys -- lost every
    remaining batch to "Cannot send a request, as the client has been closed."
    """
    ing, fake = ingest
    assert ing.upsert_catalog([_item("before-close")]) == 1

    import_common.close_http_client()      # a sibling pipeline finishes

    written = ing.upsert_catalog([_item("after-close")])
    assert written == 1, "writes after a sibling closed the shared client were lost"


# ---------------------------------------------------------------------------
# The loss report must describe THIS call, not the whole run
# ---------------------------------------------------------------------------

def test_loss_report_counts_only_this_calls_failed_batches(ingest, caplog):
    """`IngestStats` is shared -- crawl4ai_enrich.py:404 and
    firecrawl_enrich.py:381 both do `SupabaseIngest(stats=stats)` -- so
    `stats.catalog_errors` accumulates across every pipeline in the run.
    Reporting it beside THIS call's row count would state a whole-run figure
    as a fact about one upsert. Same shape as
    [[learning_aggregate_over_the_wrong_population]].
    """
    import logging
    ing, server = ingest

    # Force a failure by making the server reject everything.
    def always_500(url, headers=None, json=None, timeout=None):
        return FakeResp(500, '{"code":"XX000","message":"boom"}')

    import_common.get_http_client()          # materialise it -- the fixture is lazy
    import_common._shared_http_client.post = always_500

    ing.upsert_catalog([_item("a")])                 # 1 failed batch
    ing.stats.catalog_errors += 40                   # a sibling pipeline's failures

    with caplog.at_level(logging.ERROR):
        caplog.clear()
        ing.upsert_catalog([_item("b")])             # 1 failed batch, again

    summary = [r.getMessage() for r in caplog.records if "[catalog] wrote" in r.getMessage()]
    assert summary, "a partial write must report itself"
    assert "1 LOST across 1 failed batch(es)" in summary[0], \
        f"loss report leaked the shared counter: {summary[0]}"


# ---------------------------------------------------------------------------
# The run must FAIL when it fetched rows and then lost them
# ---------------------------------------------------------------------------
#
# This is the defect underneath all three bugs above. 107 batches were dropped
# on 2026-08-28 and `nightly-ingest` exited 0, so nothing looked at it for
# weeks. Fixing the three causes without fixing the silence just means the
# fourth cause costs another month to find.
#
# The line drawn on purpose: a WRITE loss (we had the rows and dropped them) is
# a bug and fails the run. An upstream FETCH failure (pokemontcg.io returning
# 500, as it did 20+ times in the same run) is weather -- it must not fail the
# nightly, or the signal drowns in alert fatigue.


def test_a_clean_run_records_no_write_loss(ingest):
    ing, server = ingest
    import_common.reset_write_losses()
    ing.upsert_catalog([_item("a"), _item("b")])
    assert import_common.write_loss_summary()["rows_lost"] == 0
    assert import_common.write_loss_exit_code() == 0


def test_a_partial_catalog_write_is_recorded_and_fails_the_run(ingest):
    ing, server = ingest
    import_common.reset_write_losses()
    import_common.get_http_client()
    import_common._shared_http_client.post = lambda *a, **k: FakeResp(
        500, '{"code":"XX000","message":"boom"}')

    ing.upsert_catalog([_item("a"), _item("b"), _item("c")])

    summary = import_common.write_loss_summary()
    assert summary["rows_lost"] == 3, summary
    assert summary["failed_batches"] == 1, summary
    assert import_common.write_loss_exit_code() == 1, \
        "a run that fetched rows and then dropped them must not exit 0"


def test_an_upstream_fetch_failure_does_not_fail_the_run(ingest):
    """A source being down is not our bug. Only rows we HELD and lost count."""
    ing, server = ingest
    import_common.reset_write_losses()
    ing.stats.transform_errors += 5          # e.g. pokemontcg.io 500s upstream
    ing.stats.record_warning("api.pokemontcg.io returned 500")
    assert import_common.write_loss_exit_code() == 0


def test_losses_reset_between_runs(ingest):
    ing, server = ingest
    import_common.reset_write_losses()
    import_common.get_http_client()
    import_common._shared_http_client.post = lambda *a, **k: FakeResp(500, "boom")
    ing.upsert_catalog([_item("a")])
    assert import_common.write_loss_exit_code() == 1
    import_common.reset_write_losses()
    assert import_common.write_loss_exit_code() == 0, \
        "a resumed run must not inherit the previous run's losses"


def test_market_hits_losses_also_fail_the_run(ingest):
    """The market_hits writer got the same treatment as upsert_catalog, and an
    untested second path is how the first one stayed broken. Exercise it."""
    from pipelines.import_common import MarketHit
    ing, server = ingest
    import_common.reset_write_losses()
    import_common.get_http_client()
    import_common._shared_http_client.post = lambda *a, **k: FakeResp(500, "boom")

    hits = [
        MarketHit(provider="ebay", listing_id=f"L{i}", title=f"t{i}", price=1.0,
                  currency="EUR", condition="NM", normalized_key=f"k{i}",
                  category="pokemon")
        for i in range(3)
    ]
    ing.upsert_market_hits(hits)

    summary = import_common.write_loss_summary()
    assert summary["rows_lost"] == 3, summary
    assert import_common.write_loss_exit_code() == 1


# ---------------------------------------------------------------------------
# Transient transport failures must be retried, deterministic ones must not
# ---------------------------------------------------------------------------
#
# The 2026-08-30 nightly (first run on the corrected default branch) lost 2,412
# rows across 14 batches. The three bugs fixed on 08-29 were at ZERO —
# PGRST102: 0, "client has been closed": 0 — and every remaining failure was
# transport-level:
#
#     12x  Server disconnected without sending a response
#      1x  The read operation timed out
#      1x  [SSL: WRONG_VERSION_NUMBER] wrong version number
#
# That is the classic stale keep-alive: Supabase closes an idle pooled
# connection, httpx reuses it, the write dies. The writer had NO retry, so one
# blip lost 200 rows permanently.
#
# Retrying is safe here BY CONSTRUCTION and not in general: these upserts are
# `ON CONFLICT ... DO UPDATE`, so a replay is a no-op. Contrast
# DATA_SCALING_PLAN.md §10, where retrying a market_hits load duplicated 3,000
# rows because the conflict clause could not fire against a generated PK.
#
# A deterministic rejection (PGRST102, 21000) must NOT be retried: it will fail
# identically, three times as slowly, and the retry would hide nothing.

import httpx


class _FlakyServer(FakeServer):
    """Raises a transport error on the first `fail_times` posts, then behaves."""

    def __init__(self, fail_times: int, exc: Exception | None = None):
        super().__init__()
        self.fail_times = fail_times
        self.attempts = 0
        self.exc = exc or httpx.RemoteProtocolError("Server disconnected without sending a response.")


class _FlakyClient(FakePostgrest):
    def post(self, url, headers=None, json=None, timeout=None):
        self.server.attempts += 1
        if self.server.attempts <= self.server.fail_times:
            raise self.server.exc
        return super().post(url, headers=headers, json=json, timeout=timeout)


@pytest.fixture
def flaky(monkeypatch):
    def _build(fail_times: int, exc: Exception | None = None):
        server = _FlakyServer(fail_times, exc)
        monkeypatch.setattr(import_common, "_shared_http_client", None, raising=False)
        monkeypatch.setattr(import_common, "get_http_client",
                            lambda: _ensure(server))
        # no real sleeping in tests
        monkeypatch.setattr(import_common.time, "sleep", lambda *_a, **_k: None)
        holder = {}

        def _ensure(s=server):
            cur = import_common._shared_http_client
            if cur is None or cur.is_closed:
                import_common._shared_http_client = _FlakyClient(s)
            return import_common._shared_http_client

        monkeypatch.setattr(import_common, "get_http_client", _ensure)
        ing = SupabaseIngest(batch_size=200)
        ing.enabled = True
        return ing, server
    return _build


def test_a_transient_disconnect_is_retried_and_the_rows_land(flaky):
    ing, server = flaky(fail_times=2)
    written = ing.upsert_catalog([_item("a"), _item("b")])
    assert written == 2, "rows lost to a blip that a retry would have recovered"
    assert server.attempts == 3, "should have retried twice before succeeding"
    assert len(server.accepted) == 2


def test_a_read_timeout_is_retried(flaky):
    ing, server = flaky(fail_times=1, exc=httpx.ReadTimeout("The read operation timed out"))
    assert ing.upsert_catalog([_item("a")]) == 1


def test_retries_are_bounded_and_the_loss_is_still_reported(flaky):
    """A permanently broken transport must not retry forever, and must still
    count as lost — a retry that silently gives up is the old bug again."""
    import_common.reset_write_losses()
    ing, server = flaky(fail_times=99)
    written = ing.upsert_catalog([_item("a")])
    assert written == 0
    assert server.attempts <= 5, "bounded"
    assert import_common.write_loss_summary()["rows_lost"] == 1
    assert import_common.write_loss_exit_code() == 1


def test_a_deterministic_rejection_is_NOT_retried(ingest):
    """PGRST102/21000 fail identically on replay. Retrying them wastes the
    window and hides nothing."""
    ing, server = ingest
    import_common.get_http_client()
    calls = {"n": 0}

    def always_400(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        return FakeResp(400, '{"code":"PGRST102","message":"All object keys must match"}')

    import_common._shared_http_client.post = always_400
    ing.upsert_catalog([_item("a")])
    assert calls["n"] == 1, "an HTTP rejection must be posted exactly once"


def test_a_NON_transport_exception_is_not_retried(flaky):
    """Only the absence of a response is retried.

    Widening the retryable tuple to bare Exception would replay genuine bugs —
    a TypeError in our own payload construction would be attempted three times
    and reported as a transport blip. Caught by mutation-testing: the earlier
    "deterministic rejection" test uses an HTTP RESPONSE, so it could not see
    a change to the EXCEPTION tuple at all.
    """
    ing, server = flaky(fail_times=99, exc=TypeError("a bug in our own payload"))
    ing.upsert_catalog([_item("a")])
    assert server.attempts == 1, "a non-transport error must be attempted exactly once"


def test_it_does_not_sleep_after_the_final_attempt(flaky, monkeypatch):
    """The `break` before the last sleep is the only thing stopping a pointless
    delay on the way out. The for-loop already bounds the ATTEMPTS, so counting
    attempts cannot detect its removal — count the SLEEPS."""
    slept: list[float] = []
    ing, server = flaky(fail_times=99)
    monkeypatch.setattr(import_common.time, "sleep", lambda d: slept.append(d))
    ing.upsert_catalog([_item("a")])
    assert len(slept) == import_common._POST_ATTEMPTS - 1, \
        f"expected {import_common._POST_ATTEMPTS - 1} sleeps between {import_common._POST_ATTEMPTS} attempts, got {len(slept)}"
    assert slept == sorted(slept), "backoff must not shrink"
