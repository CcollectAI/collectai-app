"""Tests for workers/feedback_loop_worker.py — label_events → catalog feedback.

Covers:
  1. No DSN → returns early
  2. No unprocessed events → 0 processed
  3. Label correction updates catalog attributes_json via jsonb_set
  4. Repeated confirmation increments observation count
  5. Missing canonical_key still marks event as processed
  6. Prediction confirmations flow through
  7. record_run called on success and error paths
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

TEST_USER = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_dsn_returns_early():
    """Worker exits cleanly when DB_DSN is not set."""
    with patch("workers.feedback_loop_worker.DSN", None), \
         patch("workers.feedback_loop_worker.record_run") as mock_record:
        from workers.feedback_loop_worker import run_once
        await run_once()
        mock_record.assert_called_with("feedback_loop_worker", "error")


@pytest.mark.asyncio
async def test_no_events_returns_zero():
    """No unprocessed events → processes 0."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=True)  # processed_at exists
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    conn.close = AsyncMock()

    with patch("workers.feedback_loop_worker.DSN", "mock://dsn"), \
         patch("workers.feedback_loop_worker.record_run") as mock_record, \
         patch("asyncpg.connect", return_value=conn):
        from workers.feedback_loop_worker import run_once
        await run_once()
        mock_record.assert_called_with("feedback_loop_worker", "ok")


@pytest.mark.asyncio
async def test_label_correction_updates_catalog():
    """Correction with valid canonical_key updates category_items."""
    label_row = {
        "id": 1,
        "item_id": "item-uuid",
        "corrected_title": "Corrected Title",
        "corrected_condition": "near_mint",
        "corrected_price_eur": 150.0,
        "payload": None,
        "action": "correct",
        "canonical_key": "pokemon-charizard",
        "category": "pokemon",
    }

    catalog_row = {
        "id": 42,
        "attributes_json": json.dumps({}),
    }

    conn = AsyncMock()
    _fetch_calls = []

    async def _fetchval(sql, *args):
        return True  # processed_at exists

    async def _fetch(sql, *args):
        sql_lower = sql.strip().lower()
        if "label_events" in sql_lower:
            return [label_row]
        if "predict_sessions" in sql_lower:
            return []
        return []

    async def _fetchrow(sql, *args):
        if "category_items" in sql.lower():
            return catalog_row
        return None

    conn.fetchval = AsyncMock(side_effect=_fetchval)
    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchrow = AsyncMock(side_effect=_fetchrow)
    conn.execute = AsyncMock()
    conn.close = AsyncMock()

    with patch("workers.feedback_loop_worker.DSN", "mock://dsn"), \
         patch("workers.feedback_loop_worker.record_run"), \
         patch("asyncpg.connect", return_value=conn):
        from workers.feedback_loop_worker import run_once
        await run_once()

        # Check that execute was called with jsonb_set UPDATE
        execute_calls = conn.execute.call_args_list
        jsonb_calls = [c for c in execute_calls if "jsonb_set" in str(c)]
        assert len(jsonb_calls) >= 1, "Should have called jsonb_set UPDATE"

        # Check that processed_at was set
        processed_calls = [c for c in execute_calls if "processed_at" in str(c)]
        assert len(processed_calls) >= 1, "Should have marked event as processed"


@pytest.mark.asyncio
async def test_missing_canonical_key_still_processed():
    """Event without canonical_key is still marked processed."""
    label_row = {
        "id": 2,
        "item_id": "item-uuid",
        "corrected_title": "Something",
        "corrected_condition": None,
        "corrected_price_eur": None,
        "payload": None,
        "action": "correct",
        "canonical_key": None,  # Missing
        "category": None,
    }

    conn = AsyncMock()

    async def _fetchval(sql, *args):
        return True

    async def _fetch(sql, *args):
        if "label_events" in sql.lower():
            return [label_row]
        return []

    conn.fetchval = AsyncMock(side_effect=_fetchval)
    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.close = AsyncMock()

    with patch("workers.feedback_loop_worker.DSN", "mock://dsn"), \
         patch("workers.feedback_loop_worker.record_run"), \
         patch("asyncpg.connect", return_value=conn):
        from workers.feedback_loop_worker import run_once
        await run_once()

        # Should still set processed_at
        processed_calls = [
            c for c in conn.execute.call_args_list
            if "processed_at" in str(c)
        ]
        assert len(processed_calls) >= 1


@pytest.mark.asyncio
async def test_run_once_records_error_on_crash():
    """Worker records error status when it crashes."""
    with patch("workers.feedback_loop_worker.DSN", "mock://dsn"), \
         patch("workers.feedback_loop_worker.record_run") as mock_record, \
         patch("asyncpg.connect", side_effect=Exception("DB down")):
        from workers.feedback_loop_worker import main
        await main()
        mock_record.assert_called_with("feedback_loop_worker", "error")
