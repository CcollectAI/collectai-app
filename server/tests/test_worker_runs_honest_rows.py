"""worker_runs rows say how long a run took, and a skip or a crash is never `ok`.

2026-09-27:
- record_run() received duration_s and never stored it; rows are written at
  completion, so every run read as "<50 ms". Self-recording workers passed no
  duration at all (datalake passed a literal 0.0).
- The orchestrator recorded `ok` for cycles it SKIPPED (DB-degraded breaker,
  light worker yielding to a heavy one).
- category_map / value_change recorded `ok` in a `finally`, i.e. also for a
  cycle that raised: value_change's 14 failures (09-09..09-12) each had an
  `ok` twin.
"""
import ast
import asyncio
import pathlib
import sys
import types

import pytest

import workers.bake_orchestrator as bo
from app import worker_registry as wr

ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Conn:
    def __init__(self, sink):
        self.sink = sink

    async def execute(self, q, *args):
        self.sink.append((q, args))


class _Pool:
    def __init__(self):
        self.sink = []

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self):
                return _Conn(pool.sink)

            async def __aexit__(self, *a):
                return False
        return _C()


@pytest.mark.asyncio
async def test_duration_reaches_the_insert():
    pool = _Pool()
    await wr._async_persist_run(pool, "w", "ok", None, 12.34)
    q, args = pool.sink[0]
    assert "duration_s" in q
    assert args[-1] == 12.34


def test_record_run_passes_duration_to_persist(monkeypatch):
    seen = {}
    monkeypatch.setattr(wr, "_persist_run_to_db",
                        lambda n, s, error_repr=None, duration_s=None: seen.update(d=duration_s))
    monkeypatch.setattr(wr, "_registry", {})
    wr.record_run("w", "ok", duration_s=7.5)
    assert seen["d"] == 7.5


@pytest.mark.asyncio
async def test_a_worker_that_records_itself_gets_the_cycle_duration(monkeypatch):
    rows = []
    monkeypatch.setattr(wr, "_persist_run_to_db",
                        lambda n, s, error_repr=None, duration_s=None: rows.append((s, duration_s)))
    monkeypatch.setattr(wr, "_registry", {})
    real_sleep = asyncio.sleep
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) > 1:
            raise asyncio.CancelledError

    async def unknown(name):
        return None

    async def run_once():
        await real_sleep(0.05)
        wr.record_run("self_recording_worker", "ok")  # no duration, like 20 workers

    mod = types.ModuleType("self_recording_worker")
    mod.run_once = run_once
    monkeypatch.setitem(sys.modules, "self_recording_worker", mod)
    monkeypatch.setattr(bo, "_seconds_since_last_run", unknown)
    monkeypatch.setattr(bo.asyncio, "sleep", fake_sleep)
    await bo._run_worker_loop("self_recording_worker", "self_recording_worker", "run_once", 3600, False)

    assert len(rows) == 1, rows
    assert rows[0][1] is not None and rows[0][1] >= 0.04


def test_outside_a_cycle_no_duration_is_invented(monkeypatch):
    seen = {}
    monkeypatch.setattr(wr, "_persist_run_to_db",
                        lambda n, s, error_repr=None, duration_s=None: seen.update(d=duration_s))
    monkeypatch.setattr(wr, "_registry", {})
    wr.record_run("w", "ok")
    assert seen["d"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["degraded", "yield"])
async def test_a_skipped_cycle_writes_no_row_and_says_why(monkeypatch, path):
    rows = []
    monkeypatch.setattr(wr, "_persist_run_to_db",
                        lambda n, s, error_repr=None, duration_s=None: rows.append(s))
    monkeypatch.setattr(wr, "_registry", {})
    name = "sanity_probe_worker"
    if path == "degraded":
        monkeypatch.setattr(bo, "_is_db_degraded", lambda: True)
    else:
        monkeypatch.setattr(bo, "_is_db_degraded", lambda: False)
        monkeypatch.setattr(bo, "_in_flight", {"valuation_worker"})
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) > 1:
            raise asyncio.CancelledError

    async def unknown(n):
        return None

    ran = []
    mod = types.ModuleType("fake_probe_mod")

    async def run_once():
        ran.append(1)
    mod.run_once = run_once
    monkeypatch.setitem(sys.modules, "fake_probe_mod", mod)
    monkeypatch.setattr(bo, "_seconds_since_last_run", unknown)
    monkeypatch.setattr(bo.asyncio, "sleep", fake_sleep)
    await bo._run_worker_loop(name, "fake_probe_mod", "run_once", 3600, False)

    assert ran == []
    assert rows == [], "a skipped cycle wrote a worker_runs row"
    assert wr._registry[name]["last_skip_reason"]
    assert "last_run" not in wr._registry[name]


def test_overdue_alert_names_the_skip_reason(monkeypatch):
    import time
    monkeypatch.setattr(wr, "_registry", {
        "sanity_probe_worker": {"last_run": time.time() - 3 * 3600, "last_status": "ok",
                                "runs": 1, "errors": 0},
    })
    wr.note_skip("sanity_probe_worker", "yielding to heavy workers ['valuation_worker']")
    od = {w["name"]: w for w in wr.get_overdue_workers()}
    assert "yielding" in od["sanity_probe_worker"]["last_skip_reason"]


def _ok_records_in_finally():
    """Every record_run(..., "ok") inside a `finally:` — it also runs when the
    body raised. AST, not grep: the status can be positional or keyword."""
    hits = []
    for p in ROOT.rglob("*.py"):
        if "tests" in p.parts or ".venv" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Try) and node.finalbody):
                continue
            for sub in node.finalbody:
                for c in ast.walk(sub):
                    if not isinstance(c, ast.Call):
                        continue
                    f = c.func
                    fname = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
                    if fname != "record_run":
                        continue
                    st = c.args[1] if len(c.args) >= 2 else None
                    for kw in c.keywords:
                        if kw.arg == "status":
                            st = kw.value
                    if st is None or (isinstance(st, ast.Constant) and st.value == "ok"):
                        hits.append(f"{p.relative_to(ROOT)}:{c.lineno}")
    return hits


def test_no_ok_is_recorded_in_a_finally():
    assert _ok_records_in_finally() == []


def test_the_finally_checker_can_see_the_pattern(tmp_path, monkeypatch):
    # Control: the checker must flag the exact shape it exists to catch.
    (tmp_path / "w.py").write_text(
        "async def run_once():\n    try:\n        pass\n    finally:\n        record_run('w', 'ok')\n"
    )
    global ROOT
    old = ROOT
    ROOT = tmp_path
    try:
        assert _ok_records_in_finally() == ["w.py:5"]
    finally:
        ROOT = old
