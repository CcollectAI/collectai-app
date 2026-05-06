"""Tests for workers.bake_orchestrator._supervised — the respawn wrapper
for monitor loops.

Closes the 2026-05-03 incident: `_health_summary_loop` went silent for 39h
because nothing was watching the watcher. `_supervised` must respawn its
inner coro when:
  - it returns normally (an "infinite" loop returning is itself a bug)
  - it raises Exception
  - it raises CancelledError mid-flight while our parent task is alive
…and must NOT loop forever when the parent task is being cancelled (i.e.,
real orchestrator shutdown).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")

from workers import bake_orchestrator  # noqa: E402


@pytest.mark.asyncio
async def test_supervised_respawns_after_clean_return():
    """An 'infinite' loop that returns once is treated as a bug — respawn."""
    calls = 0

    async def loop():
        nonlocal calls
        calls += 1
        # Return immediately — the supervisor should treat this as a bug.

    with patch.object(bake_orchestrator, "_send_telegram_alert", new=AsyncMock()):
        task = asyncio.create_task(
            bake_orchestrator._supervised(
                loop, "test_clean", initial_delay=0.01, max_delay=0.05,
            )
        )
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert calls >= 3, f"expected ≥3 respawns in 200ms, got {calls}"


@pytest.mark.asyncio
async def test_supervised_respawns_after_exception():
    """Inner coro that raises Exception should be caught and respawned."""
    calls = 0

    async def loop():
        nonlocal calls
        calls += 1
        raise RuntimeError(f"boom #{calls}")

    with patch.object(bake_orchestrator, "_send_telegram_alert", new=AsyncMock()):
        task = asyncio.create_task(
            bake_orchestrator._supervised(
                loop, "test_exc", initial_delay=0.01, max_delay=0.05,
            )
        )
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert calls >= 3, f"expected ≥3 respawns after exception, got {calls}"


@pytest.mark.asyncio
async def test_supervised_respawns_after_stray_cancel():
    """If the inner coro raises CancelledError but the parent task is NOT
    being cancelled, that's a stray mid-flight cancel — the supervisor
    should treat it as a crash and respawn, not propagate."""
    calls = 0

    async def loop():
        nonlocal calls
        calls += 1
        # Self-cancel: simulates a stray CancelledError bubbling up from
        # inside the loop while the supervisor task itself is still alive.
        raise asyncio.CancelledError("stray")

    with patch.object(bake_orchestrator, "_send_telegram_alert", new=AsyncMock()):
        task = asyncio.create_task(
            bake_orchestrator._supervised(
                loop, "test_stray_cancel", initial_delay=0.01, max_delay=0.05,
            )
        )
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert calls >= 3, (
        f"stray CancelledError should respawn, got {calls} calls"
    )


@pytest.mark.asyncio
async def test_supervised_propagates_real_shutdown_cancel():
    """When the supervisor task itself is cancelled (genuine shutdown),
    the wrapper must propagate CancelledError, not loop forever."""
    started = asyncio.Event()

    async def loop():
        started.set()
        # Block so the supervisor is sitting in this await when cancelled.
        await asyncio.sleep(60.0)

    with patch.object(bake_orchestrator, "_send_telegram_alert", new=AsyncMock()):
        task = asyncio.create_task(
            bake_orchestrator._supervised(
                loop, "test_shutdown", initial_delay=0.01, max_delay=0.05,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=1.0)
        task.cancel()
        # Should resolve in well under a second — must not loop.
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_heavy_gate_serializes_heavy_workers():
    """Two heavy workers must NOT run concurrently — the gate forces them
    through one at a time. Light workers are unaffected."""
    # Force a fresh lock for the test by clearing the module-level cache.
    bake_orchestrator._HEAVY_LOCK = None

    # Pick known heavy and light worker names from the actual sets.
    assert "valuation_worker" in bake_orchestrator._HEAVY_WORKERS
    assert "sanity_probe_worker" not in bake_orchestrator._HEAVY_WORKERS

    heavy_in_flight = 0
    max_in_flight_heavy = 0
    light_in_flight = 0
    max_in_flight_light = 0

    async def heavy_run(label):
        nonlocal heavy_in_flight, max_in_flight_heavy
        async with bake_orchestrator._heavy_gate("valuation_worker"):
            heavy_in_flight += 1
            max_in_flight_heavy = max(max_in_flight_heavy, heavy_in_flight)
            await asyncio.sleep(0.05)
            heavy_in_flight -= 1

    async def light_run(label):
        nonlocal light_in_flight, max_in_flight_light
        async with bake_orchestrator._heavy_gate("sanity_probe_worker"):
            light_in_flight += 1
            max_in_flight_light = max(max_in_flight_light, light_in_flight)
            await asyncio.sleep(0.05)
            light_in_flight -= 1

    await asyncio.gather(
        heavy_run("a"), heavy_run("b"), heavy_run("c"),
        light_run("x"), light_run("y"),
    )
    # Heavies must serialize through the lock — never more than 1 at a time.
    assert max_in_flight_heavy == 1, (
        f"heavy gate failed to serialize, max concurrent={max_in_flight_heavy}"
    )
    # Lights may overlap with each other and with heavies — gate is no-op for them.
    # We just need them to have run; their concurrency is unconstrained.
    assert max_in_flight_light >= 1


@pytest.mark.asyncio
async def test_heavy_gate_noop_for_unknown_worker():
    """Workers not in _HEAVY_WORKERS pass through the gate as no-op."""
    bake_orchestrator._HEAVY_LOCK = None

    overlapping = 0
    max_overlapping = 0

    async def light(label):
        nonlocal overlapping, max_overlapping
        async with bake_orchestrator._heavy_gate("not_a_real_worker"):
            overlapping += 1
            max_overlapping = max(max_overlapping, overlapping)
            await asyncio.sleep(0.02)
            overlapping -= 1

    await asyncio.gather(light("a"), light("b"), light("c"))
    # No serialization — all 3 should overlap.
    assert max_overlapping >= 2, (
        f"non-heavy worker should not be gated, max_overlapping={max_overlapping}"
    )


def test_register_db_error_matches_expected_signatures():
    """The breaker must catch the exact error_repr shapes we saw on 2026-05-04."""
    bake_orchestrator._db_error_window.clear()

    samples = [
        "QueryCanceledError: canceling statement due to statement timeout @ x.py:1",
        "asyncpg.exceptions.QueryCanceledError: canceling statement due to statement timeout",
        'Batch 0-200 HTTP 500: {"code":"57014","message":"canceling statement due to statement timeout"}',
        "upsert HTTP 500: code 57014",
        "upsert RPC failed: The read operation timed out",
    ]
    for s in samples:
        assert bake_orchestrator._register_db_error(s), f"missed shape: {s}"
    assert len(bake_orchestrator._db_error_window) == len(samples)


def test_register_db_error_ignores_unrelated():
    """Non-DB errors must NOT increment the breaker counter."""
    bake_orchestrator._db_error_window.clear()
    assert not bake_orchestrator._register_db_error("HTTPError 502 Bad Gateway")
    assert not bake_orchestrator._register_db_error("ValueError: invalid literal")
    assert not bake_orchestrator._register_db_error("")
    assert len(bake_orchestrator._db_error_window) == 0


def test_is_db_degraded_threshold():
    """Breaker trips once the configured number of recent errors fall in window."""
    import time as _time
    bake_orchestrator._db_error_window.clear()
    threshold = bake_orchestrator.DB_DEGRADED_THRESHOLD

    # Below threshold: not degraded.
    for _ in range(threshold - 1):
        bake_orchestrator._db_error_window.append(_time.time())
    assert not bake_orchestrator._is_db_degraded()

    # At threshold: degraded.
    bake_orchestrator._db_error_window.append(_time.time())
    assert bake_orchestrator._is_db_degraded()

    # Old errors outside window: NOT degraded.
    bake_orchestrator._db_error_window.clear()
    old = _time.time() - bake_orchestrator.DB_DEGRADED_WINDOW_S - 60
    for _ in range(threshold + 5):
        bake_orchestrator._db_error_window.append(old)
    assert not bake_orchestrator._is_db_degraded()


@pytest.mark.asyncio
async def test_supervised_only_alerts_first_n_restarts():
    """Telegram alerts should fire only on the first alert_first_n_restarts
    cycles — otherwise a wedged monitor pages every backoff tick forever."""
    calls = 0

    async def loop():
        nonlocal calls
        calls += 1
        raise RuntimeError("loop crash")

    sender = AsyncMock()
    with patch.object(bake_orchestrator, "_send_telegram_alert", new=sender):
        task = asyncio.create_task(
            bake_orchestrator._supervised(
                loop,
                "test_alert_cap",
                initial_delay=0.01,
                max_delay=0.02,
                alert_first_n_restarts=2,
            )
        )
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert sender.await_count <= 2, (
        f"expected ≤2 alerts (first_n cap), got {sender.await_count}"
    )
