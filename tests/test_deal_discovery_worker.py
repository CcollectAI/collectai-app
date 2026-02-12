"""
Tests for workers/deal_discovery_worker.py — DealDiscoveryWorker run_once().

Covers:
  1. DSN not set -> returns early without error
  2. scan returns empty list -> no pushes sent
  3. scan returns 2 deals -> push sends > 0, deals marked notified
  4. push raises exception for first deal -> continues to second
  5. scan_all_active raises exception -> agent still closed
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deal(**overrides):
    """Build a minimal deal dict matching what DealDiscoveryAgent.scan_all_active returns."""
    deal = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "listing_title": "Charizard PSA 10 Base Set",
        "listing_price": 350.00,
        "listing_url": "https://ebay.com/itm/123",
        "affiliate_url": "https://ebay.com/aff/123",
    }
    deal.update(overrides)
    return deal


def _build_pool_and_conn():
    """Create a mock asyncpg pool and connection using an async context manager."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=0)

    @asynccontextmanager
    async def _mock_acquire():
        yield mock_conn

    mock_pool = AsyncMock()
    mock_pool.acquire = _mock_acquire
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


# ---------------------------------------------------------------------------
# Fixture: disable the retry decorator so run_once can be tested directly
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_retry():
    """Disable with_async_retry so tests exercise run_once without retries/sleep."""
    def noop_retry(**kwargs):
        def decorator(fn):
            return fn
        return decorator

    with patch("workers.retry.with_async_retry", noop_retry):
        import importlib
        import workers.deal_discovery_worker as mod
        importlib.reload(mod)
        yield mod
        importlib.reload(mod)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunOnceNoDsn:
    """When DSN is not set, run_once should return immediately without error."""

    @pytest.mark.asyncio
    async def test_run_once_no_dsn(self, _patch_retry):
        mod = _patch_retry

        with patch.object(mod, "DSN", None):
            # Should not raise, just log and return
            await mod.run_once()


class TestRunOnceNoDeals:
    """When scan_all_active returns an empty list, no pushes should be sent."""

    @pytest.mark.asyncio
    async def test_run_once_no_deals(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(return_value=[])
        mock_agent.close = AsyncMock()

        mock_send = AsyncMock(return_value=1)

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with patch("app.push.send_push_to_user", mock_send):
                        await mod.run_once()

        # Agent was created, scanned, and closed
        mock_agent.scan_all_active.assert_awaited_once()
        mock_agent.close.assert_awaited_once()

        # No deals -> send_push_to_user should never be called
        mock_send.assert_not_awaited()

        # Pool should be closed
        mock_pool.close.assert_awaited_once()


class TestRunOnceWithDealsAndPush:
    """When scan returns 2 deals and push succeeds, both should be marked notified."""

    @pytest.mark.asyncio
    async def test_run_once_with_deals_and_push(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        deal_1 = _make_deal()
        deal_2 = _make_deal()
        new_deals = [deal_1, deal_2]

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(return_value=new_deals)
        mock_agent.close = AsyncMock()

        # send_push_to_user returns >0 for both deals
        mock_send = AsyncMock(return_value=1)

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with patch("app.push.send_push_to_user", mock_send):
                        await mod.run_once()

        # Push should have been called once per deal
        assert mock_send.await_count == 2

        # Each deal should have triggered an UPDATE ... SET status = 'notified'
        assert mock_conn.execute.await_count == 2
        for c in mock_conn.execute.call_args_list:
            sql = c[0][0]
            assert "notified" in sql
            assert "mandate_deals" in sql

        mock_agent.close.assert_awaited_once()
        mock_pool.close.assert_awaited_once()


class TestRunOncePushFailureContinues:
    """If push raises for the first deal, the worker should continue to the second."""

    @pytest.mark.asyncio
    async def test_run_once_push_failure_continues(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        deal_1 = _make_deal()
        deal_2 = _make_deal()
        new_deals = [deal_1, deal_2]

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(return_value=new_deals)
        mock_agent.close = AsyncMock()

        # First call raises, second call succeeds
        mock_send = AsyncMock(side_effect=[Exception("APNS timeout"), 1])

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with patch("app.push.send_push_to_user", mock_send):
                        await mod.run_once()

        # Push was attempted for both deals
        assert mock_send.await_count == 2

        # Only the second deal should have been marked notified (first push failed)
        assert mock_conn.execute.await_count == 1
        sql = mock_conn.execute.call_args_list[0][0][0]
        assert "notified" in sql

        # The UUID passed should be deal_2's id
        passed_uuid = mock_conn.execute.call_args_list[0][0][1]
        assert str(passed_uuid) == deal_2["id"]

        mock_agent.close.assert_awaited_once()
        mock_pool.close.assert_awaited_once()


class TestRunOnceAgentError:
    """If scan_all_active raises an exception, agent.close() must still be called."""

    @pytest.mark.asyncio
    async def test_run_once_agent_error(self, _patch_retry):
        mod = _patch_retry
        mock_pool, mock_conn = _build_pool_and_conn()

        mock_agent = MagicMock()
        mock_agent.scan_all_active = AsyncMock(side_effect=RuntimeError("DB connection lost"))
        mock_agent.close = AsyncMock()

        with patch.object(mod, "DSN", "mock://dsn"):
            with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
                with patch("app.agents.deal_discovery_agent.DealDiscoveryAgent", return_value=mock_agent):
                    with pytest.raises(RuntimeError, match="DB connection lost"):
                        await mod.run_once()

        # Even after error, agent.close() must be awaited (finally block)
        mock_agent.close.assert_awaited_once()

        # Pool must also be closed (outer finally block)
        mock_pool.close.assert_awaited_once()
