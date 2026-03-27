"""Tests for workers/catalog_learning_worker.py.

Mocks the DB pool to test aggregation, auto-mapping, candidate promotion.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

import pytest


# Ensure env is set before any app imports
os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("CATALOG_LEARNING_ENABLED", "true")


# ===========================================================================
# Auto-map consensus
# ===========================================================================


class TestAutoMapConsensus:
    """When 3+ unique users agree on name + existing category, auto-map."""

    @pytest.mark.asyncio
    @patch("app.db.get_pool")
    async def test_auto_maps_when_threshold_met(self, mock_get_pool):
        from workers.catalog_learning_worker import run_once

        ids = [uuid4() for _ in range(3)]

        pool = MagicMock()
        # Step 1: consensus query returns a group
        pool.fetch = AsyncMock(side_effect=[
            # consensus_rows
            [{
                "name": "charizard base set",
                "suggested_category": "pokemon",
                "cnt": 3,
                "unique_users": 3,
                "suggestion_ids": ids,
            }],
            # free_text_rows (Step 2)
            [],
            # promoted_rows (Step 3)
            [],
        ])
        # Category exists check
        pool.fetchval = AsyncMock(return_value="pokemon")

        # Mock connection for transaction
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[{"id": i} for i in ids])
        conn.execute = AsyncMock()
        conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(),
            __aexit__=AsyncMock(),
        ))

        # pool.acquire() returns async context manager
        acquire_cm = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acquire_cm)

        mock_get_pool.return_value = pool

        result = await run_once()
        assert result["auto_mapped"] == 3
        # Verify the update was called
        conn.execute.assert_called()


class TestBelowThreshold:
    """When below threshold, no auto-mapping occurs."""

    @pytest.mark.asyncio
    @patch("app.db.get_pool")
    async def test_no_action_below_threshold(self, mock_get_pool):
        from workers.catalog_learning_worker import run_once

        pool = MagicMock()
        # No consensus rows (below threshold)
        pool.fetch = AsyncMock(side_effect=[
            [],  # consensus_rows
            [],  # free_text_rows
            [],  # promoted_rows
        ])
        mock_get_pool.return_value = pool

        result = await run_once()
        assert result["auto_mapped"] == 0
        assert result["candidates_updated"] == 0
        assert result["promoted"] == 0


class TestCandidatePromotion:
    """When unique_users >= threshold in 30 days, promote to candidate."""

    @pytest.mark.asyncio
    @patch("app.db.get_pool")
    async def test_promotes_at_threshold(self, mock_get_pool):
        from workers.catalog_learning_worker import run_once

        candidate_id = uuid4()
        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=[
            [],  # consensus_rows
            # free_text_rows
            [{
                "suggested_category": "Board Games",
                "cnt": 30,
                "unique_users": 26,
                "first_seen": datetime.now(timezone.utc),
                "last_seen": datetime.now(timezone.utc),
            }],
            # promoted_rows (from UPDATE RETURNING)
            [{"id": candidate_id, "proposed_name": "Board Games"}],
        ])
        pool.fetchrow = AsyncMock(return_value=None)  # existing_candidate check
        pool.execute = AsyncMock()
        mock_get_pool.return_value = pool

        result = await run_once()
        assert result["candidates_updated"] == 1
        assert result["promoted"] == 1


class TestStaleSignalRejection:
    """Worker handles empty DB gracefully."""

    @pytest.mark.asyncio
    @patch("app.db.get_pool")
    async def test_no_pool_returns_zeros(self, mock_get_pool):
        from workers.catalog_learning_worker import run_once

        mock_get_pool.return_value = None

        result = await run_once()
        assert result == {"auto_mapped": 0, "candidates_updated": 0, "promoted": 0}


class TestIdempotency:
    """Running twice with same data produces same results."""

    @pytest.mark.asyncio
    @patch("app.db.get_pool")
    async def test_idempotent_empty_run(self, mock_get_pool):
        from workers.catalog_learning_worker import run_once

        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=[[], [], []])
        mock_get_pool.return_value = pool

        result1 = await run_once()

        pool.fetch = AsyncMock(side_effect=[[], [], []])
        result2 = await run_once()

        assert result1 == result2 == {"auto_mapped": 0, "candidates_updated": 0, "promoted": 0}
