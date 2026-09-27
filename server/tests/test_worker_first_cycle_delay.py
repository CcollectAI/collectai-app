"""A bake restart must not re-run daily and weekly workers.

2026-09-27: `_run_worker_loop` slept only the start stagger (<= 60s) and then
ran, and nothing remembered the last run — so every restart ran every worker.
7 days on prod: 43 restarts; calibration_worker (daily) 44 runs, discogs 25,
lorcast 26, ticketmaster/seatgeek (twice daily) 50 each; model_retrain_worker
(weekly) 40 runs in 30 days, 25-30 min each on the heavy gate. The loop now
reads the worker's newest worker_runs row and waits out the rest of the
interval (`_first_cycle_delay`).
"""
import asyncio

import pytest

import workers.bake_orchestrator as bo


class TestFirstCycleDelay:
    def test_ran_an_hour_ago_daily_waits_the_remaining_23h(self):
        assert bo._first_cycle_delay(86400, 7, 3600.0) == 86400 - 3600

    def test_overdue_runs_on_the_stagger(self):
        assert bo._first_cycle_delay(86400, 7, 90000.0) == 7

    def test_unknown_last_run_keeps_the_old_behaviour(self):
        # No pool / no row / query failed: never block a worker from running.
        assert bo._first_cycle_delay(86400, 7, None) == 7

    def test_clock_skew_negative_age_is_unknown_not_a_long_wait(self):
        assert bo._first_cycle_delay(86400, 7, -5.0) == 7

    def test_never_shorter_than_the_stagger(self):
        assert bo._first_cycle_delay(600, 42, 599.0) == 42


@pytest.mark.asyncio
async def test_the_loop_sleeps_the_remaining_interval_before_the_first_cycle(monkeypatch):
    """Drive the real loop: its FIRST sleep must be the remaining interval."""
    sleeps: list[float] = []
    ran: list[bool] = []

    async def fake_sleep(s):
        sleeps.append(s)
        raise asyncio.CancelledError  # stop after the first sleep

    async def ran_20_min_ago(name):
        return 1200.0

    async def run_once():
        ran.append(True)

    import types, sys
    mod = types.ModuleType("fake_daily_worker")
    mod.run_once = run_once
    monkeypatch.setitem(sys.modules, "fake_daily_worker", mod)
    monkeypatch.setattr(bo, "_seconds_since_last_run", ran_20_min_ago)
    monkeypatch.setattr(bo.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await bo._run_worker_loop("fake_daily_worker", "fake_daily_worker", "run_once", 86400, False)

    assert sleeps == [86400 - 1200]
    assert ran == [], "the worker ran before its interval was up"


def test_seed_last_run_never_overwrites_a_real_run_and_is_not_a_run(monkeypatch):
    from app import worker_registry as wr
    monkeypatch.setattr(wr, "_registry", {})
    wr.seed_last_run("w", 1000.0)
    assert wr._registry["w"]["last_run"] == 1000.0
    assert wr._registry["w"]["runs"] == 0
    wr._registry["w"]["last_run"] = 2000.0  # a real record_run() since
    wr.seed_last_run("w", 1000.0)
    assert wr._registry["w"]["last_run"] == 2000.0


@pytest.mark.asyncio
async def test_the_loop_seeds_the_admin_health_last_run(monkeypatch):
    """Without the seed, a daily worker waiting out its interval reads as
    `never_run` on the admin health page for up to a day after a deploy."""
    from app import worker_registry as wr
    import types, sys
    monkeypatch.setattr(wr, "_registry", {})

    async def fake_sleep(s):
        raise asyncio.CancelledError

    async def ran_20_min_ago(name):
        return 1200.0

    mod = types.ModuleType("fake_seeded_worker")
    mod.run_once = lambda: None
    monkeypatch.setitem(sys.modules, "fake_seeded_worker", mod)
    monkeypatch.setattr(bo, "_seconds_since_last_run", ran_20_min_ago)
    monkeypatch.setattr(bo.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await bo._run_worker_loop("fake_seeded_worker", "fake_seeded_worker", "run_once", 86400, False)

    import time
    assert abs(wr.last_recorded_at("fake_seeded_worker") - (time.time() - 1200)) < 5


@pytest.mark.asyncio
async def test_a_skipped_cycle_writes_no_worker_runs_row(monkeypatch):
    """A skip recorded as `ok` reset should_skip_recent_run's clock: discogs
    did no real run from 09-24 to 09-27 across 25 skip rows."""
    from app import worker_registry as wr
    import types, sys
    rows: list[str] = []
    monkeypatch.setattr(wr, "_persist_run_to_db", lambda n, s, error_repr=None: rows.append(s))
    monkeypatch.setattr(wr, "_registry", {})

    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) > 1:  # stagger, then the post-cycle sleep
            raise asyncio.CancelledError

    async def unknown(name):
        return None

    async def run_once():
        return wr.SKIPPED

    mod = types.ModuleType("fake_skipping_worker")
    mod.run_once = run_once
    monkeypatch.setitem(sys.modules, "fake_skipping_worker", mod)
    monkeypatch.setattr(bo, "_seconds_since_last_run", unknown)
    monkeypatch.setattr(bo.asyncio, "sleep", fake_sleep)
    await bo._run_worker_loop("fake_skipping_worker", "fake_skipping_worker", "run_once", 86400, False)

    assert len(sleeps) == 2, "the cycle never ran"
    assert rows == []


@pytest.mark.asyncio
async def test_a_real_cycle_still_writes_its_ok_row(monkeypatch):
    # Control for the test above: the same harness DOES see a row.
    from app import worker_registry as wr
    import types, sys
    rows: list[str] = []
    monkeypatch.setattr(wr, "_persist_run_to_db", lambda n, s, error_repr=None: rows.append(s))
    monkeypatch.setattr(wr, "_registry", {})
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) > 1:
            raise asyncio.CancelledError

    async def unknown(name):
        return None

    async def run_once():
        return None

    mod = types.ModuleType("fake_working_worker")
    mod.run_once = run_once
    monkeypatch.setitem(sys.modules, "fake_working_worker", mod)
    monkeypatch.setattr(bo, "_seconds_since_last_run", unknown)
    monkeypatch.setattr(bo.asyncio, "sleep", fake_sleep)
    await bo._run_worker_loop("fake_working_worker", "fake_working_worker", "run_once", 86400, False)
    assert rows == ["ok"]


def test_every_guard_call_site_returns_the_sentinel():
    # Enumerated, not listed: a new caller with a bare `return` brings the
    # clock reset back.
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    sites = 0
    for f in root.rglob("*.py"):
        if "tests" in f.parts or ".venv" in f.parts:
            continue
        src = f.read_text(errors="ignore")
        start = 0
        while (i := src.find("await should_skip_recent_run(", start)) != -1:
            sites += 1
            assert "return SKIPPED" in src[i:i + 120], f"{f}: bare return after the guard"
            start = i + 1
    assert sites >= 2


class _FakeConn:
    def __init__(self, pool):
        self.pool = pool

    async def fetch(self, q, names, host):
        self.pool.fetches += 1
        if self.pool.fail_first > 0:
            self.pool.fail_first -= 1
            raise RuntimeError("(EMAXCONNSESSION) max clients reached in session mode")
        return [{"worker_name": "a", "age": 3600.0}]

    async def fetchval(self, *a):
        self.pool.fetchvals += 1
        return 10.0


class _FakePool:
    def __init__(self, fail_first=0):
        self.fail_first = fail_first
        self.fetches = 0
        self.fetchvals = 0

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                return _FakeConn(pool)

            async def __aexit__(self_inner, *a):
                return False
        return _Ctx()


def _use_pool(monkeypatch, pool):
    import app.lib.db_helpers as dh
    monkeypatch.setattr(dh, "get_db_pool", lambda: pool)
    monkeypatch.setattr(bo, "_primed_last_run_epoch", {})


@pytest.mark.asyncio
async def test_prime_is_ONE_query_for_all_workers_and_reads_need_no_connection(monkeypatch):
    """2026-09-27 21:50: ~20 per-worker reads at once → 6 EMAXCONNSESSION →
    those 6 fell back to running. The prime must replace them."""
    pool = _FakePool()
    _use_pool(monkeypatch, pool)
    assert await bo._prime_last_run_ages(["a", "b"]) is True
    assert pool.fetches == 1
    age_a = await bo._seconds_since_last_run("a")
    age_b = await bo._seconds_since_last_run("b")
    assert pool.fetchvals == 0, "a primed worker opened its own connection"
    assert abs(age_a - 3600.0) < 5
    assert age_b is None  # no row: a new worker runs on the stagger


@pytest.mark.asyncio
async def test_a_primed_value_is_used_once_then_the_db_is_read(monkeypatch):
    # A respawned loop must not trust an hours-old startup value.
    pool = _FakePool()
    _use_pool(monkeypatch, pool)
    await bo._prime_last_run_ages(["a"])
    await bo._seconds_since_last_run("a")
    assert await bo._seconds_since_last_run("a") == 10.0
    assert pool.fetchvals == 1


@pytest.mark.asyncio
async def test_prime_retries_a_refused_connection(monkeypatch):
    pool = _FakePool(fail_first=2)
    _use_pool(monkeypatch, pool)

    async def no_sleep(s):
        return None
    monkeypatch.setattr(bo.asyncio, "sleep", no_sleep)
    assert await bo._prime_last_run_ages(["a"]) is True
    assert pool.fetches == 3


def test_start_all_workers_primes_before_it_spawns_any_loop():
    import inspect
    src = inspect.getsource(bo.start_all_workers)
    prime = src.find("await _prime_last_run_ages(")
    spawn = src.find("_run_worker_loop(")
    assert prime != -1, "start_all_workers no longer primes last-run ages"
    assert prime < spawn
