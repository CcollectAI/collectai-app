"""Tests for auto_delist_worker."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def _clear_dsn(monkeypatch):
    monkeypatch.setattr("workers.auto_delist_worker.DSN", "postgres://test")


@pytest.fixture
def _no_dsn(monkeypatch):
    monkeypatch.setattr("workers.auto_delist_worker.DSN", None)


class _DictRow(dict):
    """Minimal dict subclass that behaves like an asyncpg Record for tests."""
    pass


def _make_sale_row(sale_id="s1", listing_id="l1", item_id="i1", user_id="u1", marketplace_id="ebay"):
    return _DictRow(
        sale_id=sale_id,
        listing_id=listing_id,
        item_id=item_id,
        user_id=user_id,
        sold_marketplace_id=marketplace_id,
        sold_at=datetime.now(timezone.utc),
    )


def _make_listing_row(listing_id="l2", marketplace_id="mercari", status="active"):
    return _DictRow(id=listing_id, marketplace_id=marketplace_id, status=status)


@pytest.mark.asyncio
@patch("workers.auto_delist_worker.record_run")
@patch("workers.auto_delist_worker.asyncpg")
async def test_no_recent_sales(mock_asyncpg, mock_record_run, _clear_dsn):
    """No sales in lookback window — should log and return."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.auto_delist_worker import run_once
    await run_once()

    mock_record_run.assert_called_with("auto_delist_worker", "ok")
    mock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
@patch("workers.auto_delist_worker.record_run")
@patch("workers.auto_delist_worker.asyncpg")
async def test_sale_delists_siblings(mock_asyncpg, mock_record_run, _clear_dsn):
    """A sale should delist sibling listings for the same item."""
    mock_conn = AsyncMock()
    sale = _make_sale_row()
    sibling = _make_listing_row(listing_id="l2", marketplace_id="mercari")

    mock_conn.fetch.side_effect = [
        [sale],      # recent_sales query
        [sibling],   # sibling_listings query
    ]
    mock_conn.execute.return_value = "UPDATE 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.auto_delist_worker import run_once
    await run_once()

    assert mock_conn.execute.await_count == 1
    mock_record_run.assert_called_with("auto_delist_worker", "ok")


@pytest.mark.asyncio
@patch("workers.auto_delist_worker.record_run")
@patch("workers.auto_delist_worker.asyncpg")
async def test_already_delisted_skipped(mock_asyncpg, mock_record_run, _clear_dsn):
    """Listings already delisted should not be returned by the query."""
    mock_conn = AsyncMock()
    sale = _make_sale_row()

    mock_conn.fetch.side_effect = [
        [sale],  # recent_sales
        [],      # no active siblings (already delisted)
    ]
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.auto_delist_worker import run_once
    await run_once()

    mock_conn.execute.assert_not_awaited()
    mock_record_run.assert_called_with("auto_delist_worker", "ok")


@pytest.mark.asyncio
@patch("workers.auto_delist_worker.record_run")
async def test_no_dsn_logs_error(mock_record_run, _no_dsn):
    """Missing DB_DSN should record error and return."""
    from workers.auto_delist_worker import run_once
    await run_once()

    mock_record_run.assert_called_with("auto_delist_worker", "error")


@pytest.mark.asyncio
@patch("workers.auto_delist_worker.record_run")
@patch("workers.auto_delist_worker.asyncpg")
async def test_multiple_siblings_all_delisted(mock_asyncpg, mock_record_run, _clear_dsn):
    """Multiple siblings should all be delisted."""
    mock_conn = AsyncMock()
    sale = _make_sale_row()
    siblings = [
        _make_listing_row(listing_id="l2", marketplace_id="mercari"),
        _make_listing_row(listing_id="l3", marketplace_id="cardmarket"),
    ]

    mock_conn.fetch.side_effect = [
        [sale],     # recent_sales
        siblings,   # sibling_listings
    ]
    mock_conn.execute.return_value = "UPDATE 1"
    mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

    from workers.auto_delist_worker import run_once
    await run_once()

    assert mock_conn.execute.await_count == 2
    mock_record_run.assert_called_with("auto_delist_worker", "ok")
