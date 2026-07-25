"""Tests for worker idempotency (R15-7).

Verifies that:
1. alerts_worker.run_once() skips duplicate alerts within a 24h window.
2. vision_ingest_worker uses FOR UPDATE SKIP LOCKED to prevent double-processing.

Since both workers require a real database connection, these tests mock asyncpg
to verify the SQL logic and control flow without a live DB.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# 1. alerts_worker: duplicate alert suppression within 24h
# ---------------------------------------------------------------------------

class TestAlertsWorkerIdempotency:
    """Tests for the 24-hour dedup guard in alerts_worker.run_once()."""

    @pytest.fixture(autouse=True)
    def _patch_retry(self):
        """Disable the retry decorator so we can test run_once directly."""
        # We patch with_async_retry to be a no-op decorator
        def noop_retry(**kwargs):
            def decorator(fn):
                return fn
            return decorator

        with patch("workers.retry.with_async_retry", noop_retry):
            # Need to reimport to pick up the patched decorator
            import importlib
            import workers.alerts_worker as aw_mod
            importlib.reload(aw_mod)
            self.aw = aw_mod
            yield
            importlib.reload(aw_mod)

    @pytest.fixture()
    def mock_conn(self):
        """Create a mock asyncpg connection."""
        conn = AsyncMock()
        conn.close = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_skips_alert_already_fired_in_24h(self, mock_conn):
        """If alert_trigger_history has a recent entry, the batch query
        already excludes it via NOT EXISTS, so fetch returns empty."""
        # The _BATCH_QUERY filters out items with recent alerts via NOT EXISTS
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock()

        with patch.object(self.aw, "DSN", "mock://dsn"):
            with patch("asyncpg.connect", return_value=mock_conn):
                with patch.object(self.aw, "record_run"):
                    await self.aw.run_once()

        # Should NOT have called execute to insert a new alert
        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_fires_alert_when_no_recent_duplicate(self, mock_conn):
        """If no alert was fired in last 24h, the batch query returns the item
        and the worker inserts a new alert."""
        price_row = {
            # _BATCH_QUERY selects BOTH: `item_ref` is the catalog key (used in
            # the human-readable message) and `item_uuid` is items.id (what gets
            # persisted and routed on).
            "item_ref": "pokemon:base1-base1-99",
            "item_uuid": "4497d8bf-6e60-483a-ba97-1e3dfe6e6636",
            "q10": 2.0,
            "q50": 7.0,   # below 10
            "q90": 12.0,
            "user_id": "user-xyz",
        }
        mock_conn.fetch = AsyncMock(return_value=[price_row])
        mock_conn.execute = AsyncMock()

        with patch.object(self.aw, "DSN", "mock://dsn"):
            with patch("asyncpg.connect", return_value=mock_conn):
                with patch.object(self.aw, "record_run"):
                    with patch("workers.alerts_worker.send_push_to_user", new_callable=AsyncMock, create=True):
                        await self.aw.run_once()

        # Should have called execute to INSERT the alert
        assert mock_conn.execute.call_count >= 1
        insert_call = mock_conn.execute.call_args_list[0]
        sql = insert_call[0][0]
        assert "INSERT INTO public.alert_trigger_history" in sql

        # Regression gate (2026-07-25): item_id must be the items UUID, never
        # the catalog key. Writing item_ref here made the alerts screen and the
        # push deep-link push `/item/pokemon:base1-base1-99`, which PostgREST
        # rejects with 22P02 and the FE swallows as a warn — a blank screen.
        # Positional args are (sql, user_id, item_id, trigger_value, message).
        persisted_item_id = insert_call[0][2]
        assert persisted_item_id == "4497d8bf-6e60-483a-ba97-1e3dfe6e6636", (
            f"alert_trigger_history.item_id must be the items uuid, got {persisted_item_id!r}"
        )

    @pytest.mark.asyncio
    async def test_skips_item_with_no_owner(self, mock_conn):
        """If the item has no owner (user_id IS NULL), the batch query
        already filters it out, so fetch returns empty."""
        # _BATCH_QUERY has WHERE i.user_id IS NOT NULL
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock()

        with patch.object(self.aw, "DSN", "mock://dsn"):
            with patch("asyncpg.connect", return_value=mock_conn):
                with patch.object(self.aw, "record_run"):
                    await self.aw.run_once()

        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_item_above_threshold(self, mock_conn):
        """Items with q50 >= 10 are filtered out by the batch query
        (WHERE q50 < 10), so fetch returns empty."""
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock()

        with patch.object(self.aw, "DSN", "mock://dsn"):
            with patch("asyncpg.connect", return_value=mock_conn):
                with patch.object(self.aw, "record_run"):
                    await self.aw.run_once()

        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_item_with_none_q50(self, mock_conn):
        """Items with q50=NULL are filtered by the batch query
        (WHERE q50 IS NOT NULL), so fetch returns empty."""
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock()

        with patch.object(self.aw, "DSN", "mock://dsn"):
            with patch("asyncpg.connect", return_value=mock_conn):
                with patch.object(self.aw, "record_run"):
                    await self.aw.run_once()

        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_dsn_returns_early(self):
        """If DB_DSN is not set, run_once returns immediately."""
        with patch.object(self.aw, "DSN", None):
            # Should not raise, just return early
            await self.aw.run_once()

    @pytest.mark.asyncio
    async def test_dedup_query_checks_24h_window(self, mock_conn):
        """Verify the batch SQL contains 24-hour dedup logic via NOT EXISTS."""
        import inspect
        source = inspect.getsource(self.aw)
        # The _BATCH_QUERY should contain the 24-hour dedup check
        assert "24 hours" in source or "24h" in source.lower()
        assert "alert_trigger_history" in source
        assert "NOT EXISTS" in source


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

class TestAlertsDedupSQLStructure:
    """Verify the structure of the idempotency SQL in alerts_worker source."""

    def test_source_contains_24h_dedup(self):
        """alerts_worker should contain a 24-hour dedup query."""
        import workers.alerts_worker as aw

        source = inspect.getsource(aw)
        # Check for the dedup pattern
        assert "alert_trigger_history" in source
        assert "24 hours" in source or "24h" in source.lower()

    def test_source_checks_trigger_type(self):
        """The dedup query should filter by trigger_type."""
        import workers.alerts_worker as aw

        source = inspect.getsource(aw)
        assert "trigger_type" in source
        assert "'low_value'" in source

    def test_source_checks_user_and_item(self):
        """The dedup query should match on both user_id and item_id."""
        import workers.alerts_worker as aw

        source = inspect.getsource(aw)
        assert "user_id" in source
        assert "item_id" in source

    def test_source_inserts_after_dedup_check(self):
        """The worker should INSERT INTO alert_trigger_history after the dedup check."""
        import workers.alerts_worker as aw

        source = inspect.getsource(aw)
        # The SELECT 1 ... check comes before the INSERT
        dedup_pos = source.find("SELECT 1 FROM public.alert_trigger_history")
        insert_pos = source.find("INSERT INTO public.alert_trigger_history")
        assert dedup_pos != -1, "Missing SELECT dedup check"
        assert insert_pos != -1, "Missing INSERT statement"
        assert dedup_pos < insert_pos, "Dedup check should come before INSERT"
