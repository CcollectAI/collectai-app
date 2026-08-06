"""Tests for worker idempotency (R15-7).

Verifies that:
1. (retired) alerts_worker — deleted 2026-08-06, see below.
2. vision_ingest_worker uses FOR UPDATE SKIP LOCKED to prevent double-processing.

Since both workers require a real database connection, these tests mock asyncpg
to verify the SQL logic and control flow without a live DB.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# 1. (removed 2026-08-06) alerts_worker duplicate suppression
#
# workers/alerts_worker.py is deleted — the 'this item is valued under EUR 10'
# alert was retired as a product, not just disabled. Its 24h dedup tests went
# with it. The surviving alert path keeps the same guard: see
# deal_discovery_worker._check_watchlist_snipes (NOT EXISTS ... interval
# '24 hours' on alert_trigger_history), covered by tests/test_deal_discovery_worker.py.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 2. vision_ingest_worker: FOR UPDATE SKIP LOCKED
# ---------------------------------------------------------------------------

class TestVisionIngestSkipLocked:
    """Verify that vision_ingest_worker uses FOR UPDATE SKIP LOCKED
    to prevent concurrent workers from processing the same queue entries."""

    def test_source_contains_for_update_skip_locked(self):
        """Read the actual source code and verify the SQL contains the clause."""
        import workers.vision_ingest_worker as viw

        source = inspect.getsource(viw)
        assert "FOR UPDATE SKIP LOCKED" in source, (
            "vision_ingest_worker must use FOR UPDATE SKIP LOCKED "
            "for concurrent-safe queue processing"
        )

    def test_skip_locked_in_process_vision_queue(self):
        """Specifically check _process_vision_queue contains the clause."""
        import workers.vision_ingest_worker as viw

        func_source = inspect.getsource(viw._process_vision_queue.__wrapped__)
        assert "FOR UPDATE SKIP LOCKED" in func_source, (
            "_process_vision_queue must use FOR UPDATE SKIP LOCKED"
        )

    def test_skip_locked_query_selects_pending(self):
        """The SKIP LOCKED query should filter on status='pending'."""
        import workers.vision_ingest_worker as viw

        func_source = inspect.getsource(viw._process_vision_queue.__wrapped__)
        assert "status = 'pending'" in func_source

    def test_skip_locked_query_has_limit(self):
        """The SKIP LOCKED query should use LIMIT for batch control."""
        import workers.vision_ingest_worker as viw

        func_source = inspect.getsource(viw._process_vision_queue.__wrapped__)
        assert "LIMIT" in func_source

    @pytest.mark.asyncio
    async def test_process_vision_queue_uses_skip_locked_in_sql(self):
        """Mock asyncpg.connect and verify the actual SQL passed to fetch()
        contains FOR UPDATE SKIP LOCKED."""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])  # empty queue

        # conn.transaction() must return an async context manager
        mock_txn = MagicMock()
        mock_txn.__aenter__ = AsyncMock(return_value=None)
        mock_txn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_txn)

        # Disable retry decorator
        def noop_retry(**kwargs):
            def decorator(fn):
                return fn
            return decorator

        with patch("workers.retry.with_async_retry", noop_retry):
            import importlib
            import workers.vision_ingest_worker as viw
            importlib.reload(viw)

            with patch.object(viw, "DSN", "mock://dsn"):
                with patch("asyncpg.connect", return_value=mock_conn):
                    await viw._process_vision_queue()

            # Check the SQL in the fetch call
            assert mock_conn.fetch.call_count == 1
            sql = mock_conn.fetch.call_args[0][0]
            assert "FOR UPDATE SKIP LOCKED" in sql
            assert "vision_queue" in sql
            assert "pending" in sql

            # Cleanup
            importlib.reload(viw)


# ---------------------------------------------------------------------------
# 3. Cross-cutting: verify alerts dedup SQL structure
# ---------------------------------------------------------------------------

# TestAlertsDedupSQLStructure removed 2026-08-06 with workers/alerts_worker.py.
# It asserted that the low-value alert's dedup SELECT preceded its INSERT by
# inspecting the module source. The worker is deleted (the 'this item is worth
# under EUR 10' alert was retired), so there is nothing left to pin.
# The equivalent 24h dedup guard on the surviving alert path lives in
# deal_discovery_worker._check_watchlist_snipes (NOT EXISTS ... 24 hours).
