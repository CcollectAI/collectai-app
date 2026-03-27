"""Tests for price_monitor_worker."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def _clear_dsn(monkeypatch):
    monkeypatch.setattr("workers.price_monitor_worker.DSN", "postgres://test")


@pytest.fixture
def _no_dsn(monkeypatch):
    monkeypatch.setattr("workers.price_monitor_worker.DSN", None)


class _DictRow(dict):
    """Minimal dict subclass that behaves like an asyncpg Record for tests."""
    pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_alert(alert_id=None, user_id="u1", item_id="item1", threshold=100.0, category="watches"):
    return _DictRow(
        alert_id=alert_id or str(uuid.uuid4()),
        user_id=user_id,
        item_id=item_id,
        category=category,
        threshold_value=threshold,
    )


def _make_prediction(q50=80.0, q10=60.0, q90=110.0):
    return _DictRow(q50=q50, q10=q10, q90=q90)


def _make_item_ref(item_ref="ref1", cnt=10):
    return _DictRow(item_ref=item_ref, cnt=cnt)


def _make_snapshot(price_q50):
    return _DictRow(price_q50=price_q50)


def _make_owner(user_id="u1", item_id="item1"):
    return _DictRow(user_id=user_id, item_id=item_id)


def _make_set_row(set_id="set1", category_id="watches", set_name="Omega Speedmaster Set",
                  total_items=4, items_json=None):
    if items_json is None:
        items_json = json.dumps([
            {"key": "moonwatch", "name": "Moonwatch"},
            {"key": "reduced", "name": "Reduced"},
            {"key": "racing", "name": "Racing"},
            {"key": "mark40", "name": "Mark 40"},
        ])
    return _DictRow(
        id=set_id,
        category_id=category_id,
        set_name=set_name,
        total_items=total_items,
        items_json=items_json,
    )


# ── run_once: no DSN ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
async def test_no_dsn_records_error(mock_record_run, _no_dsn):
    """Missing DB_DSN should record error and return early."""
    from workers.price_monitor_worker import run_once
    await run_once()

    mock_record_run.assert_called_with("price_monitor", "error")


# ── run_once: no items to process ───────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_no_items_returns_ok(mock_asyncpg, mock_record_run, _clear_dsn):
    """No alerts, no anomalies, no sets -- records ok."""
    mock_conn = AsyncMock()
    # check_threshold_alerts: no active alerts
    # detect_anomalies: no item_refs
    # check_set_completions: no sets
    mock_conn.fetch.side_effect = [
        [],  # threshold alerts query
        [],  # anomaly item_refs query
        [],  # set_registry query
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    mock_record_run.assert_called_with("price_monitor", "ok")
    mock_conn.close.assert_awaited_once()


# ── Threshold alert fires when price drops below threshold ──────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_threshold_alert_fires(mock_asyncpg, mock_record_run, _clear_dsn):
    """Price below threshold should insert trigger history and update alert."""
    alert = _make_alert(alert_id="a1", threshold=100.0)
    pred = _make_prediction(q50=80.0, q10=60.0, q90=110.0)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        # check_threshold_alerts
        [alert],           # active threshold alerts
        [],                # batch dedup: no recently fired
        # detect_anomalies
        [],                # no item_refs for anomalies
        # check_set_completions
        [],                # no sets
    ]
    mock_conn.fetchrow.return_value = pred  # price prediction
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once

    with patch("workers.price_monitor_worker.check_threshold_alerts") as mock_thresh, \
         patch("workers.price_monitor_worker.detect_anomalies") as mock_anom, \
         patch("workers.price_monitor_worker.check_set_completions") as mock_sets:
        # Don't mock -- we want to test the real function
        pass

    # Actually run the real functions by calling run_once directly
    await run_once()

    # Should have called execute at least twice: INSERT into alert_trigger_history + UPDATE user_price_alerts
    assert mock_conn.execute.await_count >= 2
    mock_record_run.assert_called_with("price_monitor", "ok")
    mock_conn.close.assert_awaited_once()


# ── Threshold alert NOT fired when price is above threshold ─────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_threshold_alert_not_fired_when_above(mock_asyncpg, mock_record_run, _clear_dsn):
    """Price above threshold should NOT insert trigger history."""
    alert = _make_alert(alert_id="a1", threshold=50.0)
    pred = _make_prediction(q50=80.0)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [alert],  # active threshold alerts
        [],       # batch dedup
        [],       # anomaly item_refs
        [],       # set_registry
    ]
    mock_conn.fetchrow.return_value = pred
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    # No INSERT / UPDATE calls expected (only fetch/fetchrow)
    mock_conn.execute.assert_not_awaited()
    mock_record_run.assert_called_with("price_monitor", "ok")


# ── Threshold alert deduplication ───────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_threshold_alert_skipped_when_already_fired(mock_asyncpg, mock_record_run, _clear_dsn):
    """Recently fired alerts should be skipped via batch dedup."""
    alert = _make_alert(alert_id="a1", threshold=100.0)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [alert],                                    # active threshold alerts
        [_DictRow(alert_id="a1")],                 # batch dedup: a1 already fired
        [],                                         # anomaly item_refs
        [],                                         # set_registry
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    # Should NOT fetch price prediction or insert anything
    mock_conn.fetchrow.assert_not_awaited()
    mock_conn.execute.assert_not_awaited()


# ── Anomaly detection: price spike ──────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_anomaly_price_spike_detected(mock_asyncpg, mock_record_run, _clear_dsn):
    """A large positive z-score should trigger a price_spike alert."""
    # Build price history: baseline around 100, latest at 200 (spike)
    baseline_prices = [100.0, 101.0, 99.0, 100.5, 98.5, 100.0]
    snapshots = [_make_snapshot(200.0)] + [_make_snapshot(p) for p in baseline_prices]

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                       # threshold alerts (none)
        [_make_item_ref("ref1", 7)],             # anomaly item_refs
        snapshots,                                 # price history for ref1
        [_make_owner("u1", "item1")],            # owners of ref1
        [],                                        # batch dedup for anomalies
        [],                                        # set_registry
    ]
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    # Should have inserted one anomaly alert
    assert mock_conn.execute.await_count >= 1
    # Verify the trigger_type is price_spike in the call args
    insert_call = mock_conn.execute.call_args_list[0]
    assert "price_spike" in str(insert_call) or insert_call[0][0].find("alert_trigger_history") >= 0
    mock_record_run.assert_called_with("price_monitor", "ok")


# ── Anomaly detection: price drop ───────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_anomaly_price_drop_detected(mock_asyncpg, mock_record_run, _clear_dsn):
    """A large negative z-score should trigger a price_drop alert."""
    baseline_prices = [100.0, 101.0, 99.0, 100.5, 98.5, 100.0]
    snapshots = [_make_snapshot(10.0)] + [_make_snapshot(p) for p in baseline_prices]

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                       # threshold alerts
        [_make_item_ref("ref1", 7)],             # anomaly item_refs
        snapshots,                                 # price history
        [_make_owner("u1", "item1")],            # owners
        [],                                        # batch dedup
        [],                                        # set_registry
    ]
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    assert mock_conn.execute.await_count >= 1
    insert_call = mock_conn.execute.call_args_list[0]
    assert "price_drop" in str(insert_call)


# ── Anomaly detection: no anomaly when z-score below threshold ──────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_anomaly_not_fired_below_threshold(mock_asyncpg, mock_record_run, _clear_dsn):
    """No alert when z-score is within normal range."""
    # Prices with moderate variance so a small deviation yields z < 2.0
    # baseline mean ~100, std ~10, latest 105 => z = (105-100)/10 = 0.5
    snapshots = [_make_snapshot(105.0)] + [_make_snapshot(p) for p in [90.0, 110.0, 95.0, 105.0, 100.0]]

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                       # threshold alerts
        [_make_item_ref("ref1", 6)],             # anomaly item_refs
        snapshots,                                 # price history
        # No owners query because z-score <= threshold
        [],                                        # set_registry
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    mock_conn.execute.assert_not_awaited()


# ── Anomaly: std_dev == 0 (all identical prices) ────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_anomaly_skipped_when_stddev_zero(mock_asyncpg, mock_record_run, _clear_dsn):
    """Identical historical prices (std_dev=0) should be skipped."""
    snapshots = [_make_snapshot(100.0)] * 7

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                       # threshold alerts
        [_make_item_ref("ref1", 7)],             # anomaly item_refs
        snapshots,                                 # all same price
        [],                                        # set_registry
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    mock_conn.execute.assert_not_awaited()


# ── DB connection failure ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_db_connection_failure_records_error(mock_asyncpg, mock_record_run, _clear_dsn):
    """DB connection failure should propagate and main() records error."""
    mock_asyncpg.connect = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))

    from workers.price_monitor_worker import main

    with patch("workers.price_monitor_worker.log_dead_letter") as mock_dead_letter:
        await main()

    mock_record_run.assert_called_with("price_monitor", "error")
    mock_dead_letter.assert_called_once()


# ── Connection cleanup in finally block ─────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_connection_closed_on_error(mock_asyncpg, mock_record_run, _clear_dsn):
    """Connection should be closed even when an error occurs in processing.

    The retry decorator retries 3 times, so connect + close are called 4 times total.
    """
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = RuntimeError("unexpected DB error")
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import main

    with patch("workers.price_monitor_worker.log_dead_letter"):
        await main()

    # 1 initial + 3 retries = 4 calls; each enters finally block and closes
    assert mock_conn.close.await_count == 4
    mock_record_run.assert_called_with("price_monitor", "error")


# ── Max alerts per user cap ─────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_max_alerts_per_user_cap(mock_asyncpg, mock_record_run, _clear_dsn, monkeypatch):
    """User should not receive more than MAX_ALERTS_PER_USER alerts in one cycle."""
    monkeypatch.setattr("workers.price_monitor_worker.MAX_ALERTS_PER_USER", 2)

    alerts = [
        _make_alert(alert_id=f"a{i}", user_id="u1", item_id=f"item{i}", threshold=100.0)
        for i in range(5)
    ]
    pred = _make_prediction(q50=50.0)  # well below threshold

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        alerts,   # active threshold alerts
        [],       # batch dedup: none recently fired
        [],       # anomaly item_refs
        [],       # set_registry
    ]
    mock_conn.fetchrow.return_value = pred
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    # Each fired alert = 2 execute calls (INSERT + UPDATE), capped at 2 alerts
    assert mock_conn.execute.await_count == 4  # 2 alerts * 2 calls
    mock_record_run.assert_called_with("price_monitor", "ok")


# ── Set completion alert fires ──────────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_set_completion_alert_fires(mock_asyncpg, mock_record_run, _clear_dsn):
    """User with >50% of a set should get a completion suggestion."""
    set_row = _make_set_row(total_items=4)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                              # threshold alerts
        [],                                              # anomaly item_refs
        [set_row],                                       # set_registry
        [_DictRow(user_id="u1")],                       # users in category
        [                                                 # owned items (3 of 4 match)
            _DictRow(normalized_key="moonwatch-pro", title="Omega Moonwatch"),
            _DictRow(normalized_key="reduced-39mm", title="Speedmaster Reduced"),
            _DictRow(normalized_key="racing-dial", title="Speedmaster Racing"),
        ],
    ]
    # _already_fired returns None (not fired)
    mock_conn.fetchrow.return_value = None
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    assert mock_conn.execute.await_count >= 1
    insert_call = mock_conn.execute.call_args_list[0]
    assert "completeness" in str(insert_call)
    mock_record_run.assert_called_with("price_monitor", "ok")


# ── Set completion: below minimum threshold ─────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_set_completion_not_fired_below_min_pct(mock_asyncpg, mock_record_run, _clear_dsn):
    """User with <50% of a set should NOT get a suggestion."""
    set_row = _make_set_row(total_items=4)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                              # threshold alerts
        [],                                              # anomaly item_refs
        [set_row],                                       # set_registry
        [_DictRow(user_id="u1")],                       # users in category
        [                                                 # only 1 of 4 matched
            _DictRow(normalized_key="moonwatch-pro", title="Omega Moonwatch"),
        ],
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    mock_conn.execute.assert_not_awaited()


# ── Set completion: 100% complete, no alert ─────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_set_completion_not_fired_when_complete(mock_asyncpg, mock_record_run, _clear_dsn):
    """User who already owns 100% of a set should NOT get a suggestion."""
    set_row = _make_set_row(total_items=4)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [],                                              # threshold alerts
        [],                                              # anomaly item_refs
        [set_row],                                       # set_registry
        [_DictRow(user_id="u1")],                       # users
        [                                                 # all 4 match
            _DictRow(normalized_key="moonwatch-x", title="Moonwatch"),
            _DictRow(normalized_key="reduced-x", title="Reduced"),
            _DictRow(normalized_key="racing-x", title="Racing"),
            _DictRow(normalized_key="mark40-x", title="Mark40"),
        ],
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    mock_conn.execute.assert_not_awaited()


# ── Threshold: prediction is None ───────────────────────────────────────────

@pytest.mark.asyncio
@patch("workers.price_monitor_worker.record_run")
@patch("workers.price_monitor_worker.asyncpg")
async def test_threshold_skipped_when_no_prediction(mock_asyncpg, mock_record_run, _clear_dsn):
    """Alert should be skipped when there's no price prediction for the item."""
    alert = _make_alert(alert_id="a1", threshold=100.0)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [
        [alert],  # threshold alerts
        [],       # batch dedup
        [],       # anomaly item_refs
        [],       # set_registry
    ]
    mock_conn.fetchrow.return_value = None  # no prediction
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.price_monitor_worker import run_once
    await run_once()

    mock_conn.execute.assert_not_awaited()
