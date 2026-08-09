"""Tests for valuation_worker."""
from __future__ import annotations

import datetime
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# Pre-inject a mock for app.ml.model_loader so the lazy import inside run_once works
_mock_model_loader = MagicMock()
_mock_model_loader.get_active_model = AsyncMock(return_value=None)


@pytest.fixture(autouse=True)
def _mock_ml_module(monkeypatch):
    """Ensure app.ml.model_loader is always importable as a mock."""
    monkeypatch.setitem(sys.modules, "app.ml.model_loader", _mock_model_loader)
    # Reset the mock between tests
    _mock_model_loader.get_active_model = AsyncMock(return_value=None)


@pytest.fixture
def _clear_dsn(monkeypatch):
    monkeypatch.setattr("workers.valuation_worker.DSN", "postgres://test")


@pytest.fixture
def _no_dsn(monkeypatch):
    monkeypatch.setattr("workers.valuation_worker.DSN", None)


class _DictRow(dict):
    """Minimal dict subclass that behaves like an asyncpg Record for tests."""

    def __getitem__(self, key):
        return super().__getitem__(key)


def _make_hit_row(
    hit_id="h1",
    item_ref="watches:rolex-submariner",
    source="ebay",
    price=150.0,
    observed_at=None,
    condition=None,
    attrs=None,
):
    if observed_at is None:
        observed_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
    return _DictRow(
        id=hit_id,
        item_ref=item_ref,
        source=source,
        price=price,
        observed_at=observed_at,
        condition=condition,
        attrs=attrs,
    )


# ---------------------------------------------------------------------------
# 1. No DSN — run_once returns early (no record_run call, no DB connection)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.record_run")
async def test_no_dsn_returns_early(mock_record_run, _no_dsn):
    """Missing DB_DSN should return early without calling record_run."""
    from workers.valuation_worker import run_once

    await run_once()

    # run_once logs error and returns; record_run is NOT called inside run_once
    # when DSN is missing (record_run("ok") is after the main logic)
    mock_record_run.assert_not_called()


# ---------------------------------------------------------------------------
# 2. No items needing valuation — records ok
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.record_run")
@patch("workers.valuation_worker.asyncpg")
async def test_no_unprocessed_hits(mock_asyncpg, mock_record_run, _clear_dsn):
    """No unprocessed market_hits — should return early and record ok."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.valuation_worker import run_once

    await run_once()

    # The worker returns before record_run when no hits (just returns from try block)
    # but still closes connection
    mock_conn.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. Successful valuation of a single item
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.record_run")
@patch("workers.valuation_worker.asyncpg")
async def test_single_item_valuation(mock_asyncpg, mock_record_run, _clear_dsn):
    """Single item with market hits should produce a price prediction."""
    mock_conn = AsyncMock()
    hits = [
        _make_hit_row("h1", "watches:rolex", "ebay", 100.0),
        _make_hit_row("h2", "watches:rolex", "mercari", 120.0),
        _make_hit_row("h3", "watches:rolex", "ebay", 110.0),
    ]
    mock_conn.fetch.return_value = hits
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    # Patch model loader to avoid import errors
    with patch("workers.valuation_worker.run_once.__wrapped__", None, create=True):
        pass

    from workers.valuation_worker import run_once

    await run_once()

    # Should have 3 execute calls: INSERT price_predictions, INSERT price_history, UPDATE market_hits
    assert mock_conn.execute.await_count == 3

    # Verify the price_predictions INSERT
    first_call_args = mock_conn.execute.call_args_list[0]
    sql = first_call_args[0][0]
    assert "price_predictions" in sql
    item_ref_arg = first_call_args[0][1]
    assert item_ref_arg == "watches:rolex"

    # Verify price_history INSERT
    second_call_args = mock_conn.execute.call_args_list[1]
    assert "price_history" in second_call_args[0][0]

    # Verify market_hits UPDATE
    third_call_args = mock_conn.execute.call_args_list[2]
    assert "UPDATE" in third_call_args[0][0]
    assert "market_hits" in third_call_args[0][0]

    mock_record_run.assert_called_with("valuation_worker", "ok")
    mock_conn.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. Batch processing — multiple item_ref groups
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.record_run")
@patch("workers.valuation_worker.asyncpg")
async def test_batch_multiple_items(mock_asyncpg, mock_record_run, _clear_dsn):
    """Multiple item_ref groups should each get their own valuation."""
    mock_conn = AsyncMock()
    hits = [
        _make_hit_row("h1", "watches:rolex", "ebay", 100.0),
        _make_hit_row("h2", "watches:rolex", "mercari", 120.0),
        _make_hit_row("h3", "sneakers:jordan1", "stockx", 200.0),
        _make_hit_row("h4", "sneakers:jordan1", "ebay", 210.0),
        _make_hit_row("h5", "sneakers:jordan1", "mercari", 190.0),
    ]
    mock_conn.fetch.return_value = hits
    mock_conn.execute.return_value = "INSERT 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.valuation_worker import run_once

    await run_once()

    # 2 groups × 3 calls each (predictions, history, update) = 6
    assert mock_conn.execute.await_count == 6
    mock_record_run.assert_called_with("valuation_worker", "ok")
    mock_conn.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. DB connection failure — exception propagates (retry decorator re-raises)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("workers.valuation_worker.record_run")
@patch("workers.valuation_worker.asyncpg")
async def test_db_connection_failure(mock_asyncpg, mock_record_run, mock_sleep, _clear_dsn):
    """DB connection failure should raise (retry decorator exhausts retries)."""
    mock_asyncpg.connect = AsyncMock(side_effect=ConnectionRefusedError("connection refused"))

    from workers.valuation_worker import run_once

    with pytest.raises(ConnectionRefusedError):
        await run_once()

    # record_run should NOT be called (error is recorded in main(), not run_once())
    mock_record_run.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Connection cleanup in finally block
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("workers.valuation_worker.record_run")
@patch("workers.valuation_worker.asyncpg")
async def test_connection_closed_on_error(mock_asyncpg, mock_record_run, mock_sleep, _clear_dsn):
    """Connection should be closed even if processing fails mid-way."""
    mock_conn = AsyncMock()
    hits = [_make_hit_row("h1", "watches:rolex", "ebay", 100.0)]
    mock_conn.fetch.return_value = hits
    # First execute (price_predictions INSERT) fails
    mock_conn.execute.side_effect = Exception("DB write error")
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.valuation_worker import run_once

    with pytest.raises(Exception, match="DB write error"):
        await run_once()

    # Connection should be closed via finally block on every retry attempt (4 total: 1 + 3 retries)
    assert mock_conn.close.await_count == 4
    # record_run("ok") should NOT have been called since we errored
    mock_record_run.assert_not_called()


# ---------------------------------------------------------------------------
# 7. main() records error on exception
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.log_dead_letter")
@patch("workers.valuation_worker.record_run")
async def test_main_records_error_on_crash(mock_record_run, mock_log_dead_letter, _no_dsn):
    """main() should catch exceptions and record error."""
    from workers.valuation_worker import main

    # Patch run_once to raise
    with patch("workers.valuation_worker.run_once", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        await main()

    mock_record_run.assert_called_with("valuation_worker", "error")
    mock_log_dead_letter.assert_called_once()


# ---------------------------------------------------------------------------
# 8. _build_evidence produces correct structure
# ---------------------------------------------------------------------------
def test_build_evidence_structure():
    """_build_evidence should return hit_ids, summary dict, and explanation text."""
    from workers.valuation_worker import _build_evidence

    now = datetime.datetime.now(datetime.timezone.utc)
    hits = [
        {"id": "h1", "source": "ebay", "price": 100.0, "observed_at": now},
        {"id": "h2", "source": "ebay", "price": 120.0, "observed_at": now - datetime.timedelta(days=10)},
        {"id": "h3", "source": "mercari", "price": 110.0, "observed_at": now},
    ]

    hit_ids, summary, explanation = _build_evidence(hits)

    assert hit_ids == ["h1", "h2", "h3"]
    assert summary["total_comps"] == 3
    assert len(summary["sources"]) == 2  # ebay + mercari
    # "eBay sales", not "eBay sold listings". Every row reaching _build_evidence
    # is a SOLD comp — the query filters `is_listing IS NOT TRUE` — so calling
    # them listings was wrong for every source, and "eBay sold" + "listings"
    # read as "2 eBay sold listings". Changed 2026-08-07 alongside adding
    # `sparrow_p2p`, which would otherwise have rendered "1 Sparrow P2p listing"
    # for a completed member sale.
    assert "eBay sales" in explanation
    assert "Mercari sale" in explanation
    assert "listing" not in explanation, "a sold comp is not a listing"
    assert "90 days" in explanation


# ---------------------------------------------------------------------------
# 9. _predict_ridge returns prediction when model is valid
# ---------------------------------------------------------------------------
def test_predict_quantile_valid_model():
    """_predict_quantile should return a positive prediction for a valid model."""
    from workers.valuation_worker import _predict_quantile

    model = {
        "standardizer": {"mean": [0.5], "std": [0.2]},
        "ridge": {"coef": [1.5], "intercept": 100.0},
        "features": ["condition_score"],
    }

    result = _predict_quantile(model, {"condition_score": 0.7}, "ridge")
    assert result is not None
    assert result > 0


def test_predict_quantile_mismatched_dimensions():
    """_predict_quantile should return None when dimensions don't match."""
    from workers.valuation_worker import _predict_quantile

    model = {
        "standardizer": {"mean": [0.5, 0.5], "std": [0.2, 0.2]},
        "ridge": {"coef": [1.5], "intercept": 100.0},  # coef has 1, mean has 2
        "features": ["condition_score", "rarity_score"],
    }

    result = _predict_quantile(model, {"condition_score": 0.7}, "ridge")
    assert result is None


def test_predict_quantile_broken_model():
    """_predict_quantile should return None for a broken/missing-head model dict."""
    from workers.valuation_worker import _predict_quantile

    result = _predict_quantile({}, {"condition_score": 0.7}, "ridge")
    assert result is None


# ---------------------------------------------------------------------------
# 10. SQL query filters out NULL item_ref rows
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.record_run")
@patch("workers.valuation_worker.asyncpg")
async def test_null_item_ref_filtered_by_query(mock_asyncpg, mock_record_run, _clear_dsn):
    """The SQL query must include 'AND item_ref IS NOT NULL' to prevent TypeError."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.valuation_worker import run_once

    await run_once()

    # Verify the SQL query includes the NULL filter
    fetch_call = mock_conn.fetch.call_args
    sql = fetch_call[0][0]
    assert "item_ref IS NOT NULL" in sql, (
        "Query must filter NULL item_ref to prevent 'argument of type NoneType is not iterable' crash"
    )


# ---------------------------------------------------------------------------
# 11. Required env var DB_DSN is validated
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("workers.valuation_worker.record_run")
async def test_dsn_env_required(mock_record_run, _no_dsn):
    """run_once should return early when DB_DSN is not set."""
    from workers.valuation_worker import run_once

    await run_once()

    # Should not call record_run — just logs error and returns
    mock_record_run.assert_not_called()


# ---------------------------------------------------------------------------
# 12. Valuation scheduler validates DB_DSN on startup
# ---------------------------------------------------------------------------
def test_scheduler_exits_without_dsn(monkeypatch):
    """Scheduler main() should exit(1) if DB_DSN is missing."""
    monkeypatch.delenv("DB_DSN", raising=False)

    from workers.valuation_scheduler import main

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
