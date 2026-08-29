"""Tests for workers/catalog_learning_worker.py.

Mocks the DB connection to test aggregation, auto-mapping, candidate promotion.

2026-07-27: these patched `app.db.get_pool`, which this worker does not call
and never imports (grep: 0 occurrences). It was migrated to a DIRECT
connection — `asyncpg.connect(DB_DSN_DIRECT or DB_DSN)`, then
`pool = conn` to keep the existing `pool.X` call sites working. With no DSN
in the test environment, run_once() returns at the guard on line ~48 with
{auto_mapped: 0, candidates_updated: 0, promoted: 0}, which is why the
assertions read `assert 0 == 3`.

So the worker was fine and the mock was aimed at nothing. Patching `asyncpg.connect` instead, and giving the
guard a DSN to get past.
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
# run_once() returns all-zeros immediately without one.
#
# NOT setdefault. `ci-min.yml` runs this suite with `DB_DSN: ""`, and
# setdefault only fires when the key is ABSENT -- an empty string is a present
# value, so it no-opped and the guard tripped anyway. These two tests therefore
# passed locally (DB_DSN unset) and failed in CI (DB_DSN set to ""), which is
# why they sat in the "known-stale" pile behind continue-on-error.
# Same shape as `or 0` turning UNKNOWN into "fine": empty is not absent.
if not os.environ.get("DB_DSN"):
    os.environ["DB_DSN"] = "postgresql://mock/mock"


# ===========================================================================
# Auto-map consensus
# ===========================================================================


class TestAutoMapConsensus:
    """When 3+ unique users agree on name + existing category, auto-map."""

    @pytest.mark.asyncio
    @patch("asyncpg.connect", new_callable=AsyncMock)
    async def test_auto_maps_when_threshold_met(self, mock_connect):
        from workers.catalog_learning_worker import run_once

        ids = [uuid4() for _ in range(3)]

        # ONE connection object. The worker does `pool = conn` after
        # asyncpg.connect(), so pool.fetch and conn.fetch are the SAME mock —
        # the old test's separate `conn` + pool.acquire() setup was modelling
        # a pool that no longer exists, and every fetch inside the
        # transaction silently consumed the next side_effect entry meant for
        # a later step (StopAsyncIteration).
        #
        # Real fetch order through run_once():
        #   1. consensus_rows        (step 1)
        #   2. locked                (inside conn.transaction(), FOR UPDATE)
        #   3. user_rows             (who to push-notify)
        #   4. free_text_rows        (step 2)
        #   5. promoted_rows         (step 3, UPDATE ... RETURNING)
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=[
            [{
                "name": "charizard base set",
                "suggested_category": "pokemon",
                "cnt": 3,
                "unique_users": 3,
                "suggestion_ids": ids,
            }],
            [{"id": i} for i in ids],   # locked — all 3 acquired
            [],                          # user_rows — nobody to notify
            [],                          # free_text_rows
            [],                          # promoted_rows
        ])
        conn.fetchval = AsyncMock(return_value="pokemon")  # category exists
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()

        _tx = MagicMock()
        _tx.__aenter__ = AsyncMock(return_value=None)
        _tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=_tx)

        mock_connect.return_value = conn

        result = await run_once()
        assert result["auto_mapped"] == 3
        # The UPDATE ... SET status='mapped' actually ran.
        assert any(
            "status = 'mapped'" in str(c) for c in conn.execute.call_args_list
        ), conn.execute.call_args_list


class TestBelowThreshold:
    """When below threshold, no auto-mapping occurs."""

    @pytest.mark.asyncio
    @patch("asyncpg.connect", new_callable=AsyncMock)
    async def test_no_action_below_threshold(self, mock_connect):
        from workers.catalog_learning_worker import run_once

        pool = AsyncMock()
        # No consensus rows (below threshold)
        pool.fetch = AsyncMock(side_effect=[
            [],  # consensus_rows
            [],  # free_text_rows
            [],  # promoted_rows
        ])
        mock_connect.return_value = pool

        result = await run_once()
        assert result["auto_mapped"] == 0
        assert result["candidates_updated"] == 0
        assert result["promoted"] == 0


class TestCandidatePromotion:
    """When unique_users >= threshold in 30 days, promote to candidate."""

    @pytest.mark.asyncio
    @patch("asyncpg.connect", new_callable=AsyncMock)
    async def test_promotes_at_threshold(self, mock_connect):
        from workers.catalog_learning_worker import run_once

        candidate_id = uuid4()
        pool = AsyncMock()
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
        mock_connect.return_value = pool

        result = await run_once()
        assert result["candidates_updated"] == 1
        assert result["promoted"] == 1


class TestStaleSignalRejection:
    """Worker handles empty DB gracefully."""

    @pytest.mark.asyncio
    @patch("asyncpg.connect", new_callable=AsyncMock)
    async def test_no_dsn_returns_zeros(self, mock_connect, monkeypatch):
        """Was test_no_pool_returns_zeros.

        The worker no longer takes a pool, so "no pool" is not a state it can
        be in. The equivalent guard is a missing DSN: run_once() logs, records
        an error run, and returns all-zeros WITHOUT connecting.
        """
        from workers.catalog_learning_worker import run_once

        monkeypatch.delenv("DB_DSN", raising=False)
        monkeypatch.delenv("DB_DSN_DIRECT", raising=False)

        result = await run_once()
        assert result == {"auto_mapped": 0, "candidates_updated": 0, "promoted": 0}
        mock_connect.assert_not_awaited()


class TestIdempotency:
    """Running twice with same data produces same results."""

    @pytest.mark.asyncio
    @patch("asyncpg.connect", new_callable=AsyncMock)
    async def test_idempotent_empty_run(self, mock_connect):
        from workers.catalog_learning_worker import run_once

        pool = AsyncMock()
        pool.fetch = AsyncMock(side_effect=[[], [], []])
        mock_connect.return_value = pool

        result1 = await run_once()

        pool.fetch = AsyncMock(side_effect=[[], [], []])
        result2 = await run_once()

        assert result1 == result2 == {"auto_mapped": 0, "candidates_updated": 0, "promoted": 0}
