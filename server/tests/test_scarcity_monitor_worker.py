"""Tests for scarcity_monitor_worker."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _set_dsn(monkeypatch):
    monkeypatch.setenv("DB_DSN", "postgresql://test:test@localhost:5432/test")


@pytest.fixture
def _mock_record_run():
    with patch("workers.scarcity_monitor_worker.record_run") as mock_rr:
        yield mock_rr


@pytest.fixture
def _mock_connect():
    """Provide a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    with patch("workers.scarcity_monitor_worker.asyncpg.connect", return_value=conn) as mock_conn:
        yield conn


@pytest.mark.asyncio
async def test_scarcity_monitor_fires_alerts(_mock_connect, _mock_record_run):
    """Scarce items with score > 0.5 should insert alert_trigger_history entries."""
    conn = _mock_connect

    scarce_items = [
        {
            "category": "pokemon",
            "item_key": "charizard-base-holo",
            "recent_demand": 20,
            "prev_demand": 5,
            "demand_growth_pct": 3.0,
            "recent_supply": 2.0,
            "prev_supply": 10.0,
            "supply_decline_pct": 0.8,
            "scarcity_score": 0.75,
        },
    ]

    # Mock interested users
    conn.fetch.return_value = [
        {"user_id": "user-1", "item_id": "item-1"},
        {"user_id": "user-2", "item_id": "item-2"},
    ]

    # No dedup hit
    conn.fetchrow.return_value = None

    with patch(
        "app.features.data_moat.detect_scarcity",
        new_callable=AsyncMock,
        return_value=scarce_items,
    ):
        from workers.scarcity_monitor_worker import run_once
        await run_once()

    # Should have inserted alerts for both users
    assert conn.execute.call_count == 2
    for call in conn.execute.call_args_list:
        assert "alert_trigger_history" in call[0][0]
        assert "'scarcity'" in call[0][0]  # trigger_type in SQL literal

    # record_run called with ok
    _mock_record_run.assert_called_with("scarcity_monitor_worker", "ok")


@pytest.mark.asyncio
async def test_scarcity_monitor_dedup(_mock_connect, _mock_record_run):
    """If alert already fired recently, should skip that user."""
    conn = _mock_connect

    scarce_items = [
        {
            "category": "funko",
            "item_key": "batman-89",
            "scarcity_score": 0.9,
            "demand_growth_pct": 2.0,
            "supply_decline_pct": 0.6,
            "recent_demand": 15,
            "recent_supply": 3.0,
        },
    ]

    # One interested user
    conn.fetch.return_value = [
        {"user_id": "user-1", "item_id": "item-1"},
    ]

    # Dedup: already fired
    conn.fetchrow.return_value = {"exists": 1}

    with patch(
        "app.features.data_moat.detect_scarcity",
        new_callable=AsyncMock,
        return_value=scarce_items,
    ):
        from workers.scarcity_monitor_worker import run_once
        await run_once()

    # No alerts should be inserted (dedup blocked it)
    conn.execute.assert_not_called()
    _mock_record_run.assert_called_with("scarcity_monitor_worker", "ok")


@pytest.mark.asyncio
async def test_scarcity_monitor_empty_result(_mock_connect, _mock_record_run):
    """Empty scarcity results should still call record_run."""
    with patch(
        "app.features.data_moat.detect_scarcity",
        new_callable=AsyncMock,
        return_value=[],
    ):
        from workers.scarcity_monitor_worker import run_once
        await run_once()

    _mock_record_run.assert_called_with("scarcity_monitor_worker", "ok")


@pytest.mark.asyncio
async def test_scarcity_monitor_below_threshold(_mock_connect, _mock_record_run):
    """Items with scarcity_score <= 0.5 should not trigger alerts."""
    conn = _mock_connect

    scarce_items = [
        {
            "category": "mtg",
            "item_key": "black-lotus",
            "scarcity_score": 0.3,
            "demand_growth_pct": 0.5,
            "supply_decline_pct": 0.4,
            "recent_demand": 8,
            "recent_supply": 5.0,
        },
    ]

    with patch(
        "app.features.data_moat.detect_scarcity",
        new_callable=AsyncMock,
        return_value=scarce_items,
    ):
        from workers.scarcity_monitor_worker import run_once
        await run_once()

    # No user lookups or alert inserts
    conn.fetch.assert_not_called()
    conn.execute.assert_not_called()
    _mock_record_run.assert_called_with("scarcity_monitor_worker", "ok")


@pytest.mark.asyncio
async def test_scarcity_monitor_no_dsn(_mock_record_run, monkeypatch):
    """Missing DSN should record error."""
    monkeypatch.setenv("DB_DSN", "")
    # Force re-evaluation
    import workers.scarcity_monitor_worker as mod
    mod.DSN = ""

    await mod.run_once()
    _mock_record_run.assert_called_with("scarcity_monitor_worker", "error")

    # Restore
    mod.DSN = "postgresql://test:test@localhost:5432/test"
