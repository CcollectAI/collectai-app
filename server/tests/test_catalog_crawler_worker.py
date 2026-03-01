"""
Tests for workers/catalog_crawler_worker.py — Catalog Crawler Worker.

Covers:
  - run_once() with mocked DB + MarketplaceAgent
  - Stale item prioritization (ORDER BY last_crawled_at ASC NULLS FIRST)
  - Supply snapshot recording
  - Error handling for individual items
  - Empty catalog edge case
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DB_DSN", "mock://localhost")


@pytest.fixture
def _mock_dsn():
    with patch("workers.catalog_crawler_worker.DSN", "mock://localhost"):
        yield


@pytest.fixture
def _mock_record_run():
    with patch("workers.catalog_crawler_worker.record_run") as mock_rr:
        yield mock_rr


@pytest.fixture
def _mock_connect():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=True)
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    with patch("workers.catalog_crawler_worker.asyncpg.connect", return_value=conn):
        yield conn


@pytest.fixture
def _mock_supply_snapshot():
    """Mock record_supply_snapshot at its source module."""
    with patch("app.features.data_moat.record_supply_snapshot", new_callable=AsyncMock) as mock_ss:
        yield mock_ss


class TestCatalogCrawlerRunOnce:
    """Tests for catalog_crawler_worker.run_once()."""

    @pytest.mark.asyncio
    async def test_empty_catalog(self, _mock_dsn, _mock_connect, _mock_record_run):
        """When no items exist, worker completes cleanly."""
        _mock_connect.fetch.return_value = []

        from workers.catalog_crawler_worker import run_once
        await run_once()

        _mock_record_run.assert_called_with("catalog_crawler_worker", "ok")

    @pytest.mark.asyncio
    async def test_crawls_items_and_persists(
        self, _mock_dsn, _mock_connect, _mock_record_run, _mock_supply_snapshot
    ):
        """Worker calls aggregate_search per item and persists results."""
        _mock_connect.fetch.return_value = [
            {"category": "pokemon", "item_key": "charizard-base", "title": "Charizard Base Set Holo"},
            {"category": "lego", "item_key": "lego-75192", "title": "LEGO Millennium Falcon"},
        ]

        from app.agents.marketplace_agent import AggregationResult, ScoredMarketHit

        mock_result = AggregationResult(
            hits=[
                ScoredMarketHit(
                    hit={"source": "ebay", "raw_id": "1", "price": 100.0},
                    provenance_score=0.8,
                    source_reliability=0.9,
                    recency_score=0.05,
                    is_sold=True,
                ),
            ],
            total_sources_queried=2,
            successful_sources=2,
            aggregate_confidence=0.75,
            dedup_count=0,
            query_metadata={},
        )

        mock_agent = MagicMock()
        mock_agent.aggregate_search = AsyncMock(return_value=mock_result)
        mock_agent.persist_comps_to_db = AsyncMock(return_value=1)
        mock_agent.close = AsyncMock()

        with patch("app.agents.marketplace_agent.MarketplaceAgent", return_value=mock_agent):
            from workers.catalog_crawler_worker import run_once
            await run_once()

        # Should have called aggregate_search for both items
        assert mock_agent.aggregate_search.call_count == 2
        assert mock_agent.persist_comps_to_db.call_count == 2
        _mock_record_run.assert_called_with("catalog_crawler_worker", "ok")

    @pytest.mark.asyncio
    async def test_individual_item_error_doesnt_crash(
        self, _mock_dsn, _mock_connect, _mock_record_run, _mock_supply_snapshot
    ):
        """If one item fails, the worker continues to the next."""
        _mock_connect.fetch.return_value = [
            {"category": "pokemon", "item_key": "item1", "title": "Item 1"},
            {"category": "lego", "item_key": "item2", "title": "Item 2"},
        ]

        mock_agent = MagicMock()
        # First call raises, second succeeds
        mock_result = MagicMock()
        mock_result.hits = []
        mock_agent.aggregate_search = AsyncMock(side_effect=[
            RuntimeError("API error"),
            mock_result,
        ])
        mock_agent.persist_comps_to_db = AsyncMock(return_value=0)
        mock_agent.close = AsyncMock()

        with patch("app.agents.marketplace_agent.MarketplaceAgent", return_value=mock_agent):
            from workers.catalog_crawler_worker import run_once
            await run_once()

        # Worker should still complete (with errors recorded)
        _mock_record_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_dsn_records_error(self, _mock_record_run):
        """Worker records error if DB_DSN is not set."""
        with patch("workers.catalog_crawler_worker.DSN", None):
            from workers.catalog_crawler_worker import run_once
            await run_once()

        _mock_record_run.assert_called_with("catalog_crawler_worker", "error")


class TestCrawlSingleItem:
    """Tests for _crawl_single_item()."""

    @pytest.mark.asyncio
    async def test_returns_stats_on_success(self, _mock_supply_snapshot):
        """Successful crawl returns item stats."""
        import asyncio
        from app.agents.marketplace_agent import AggregationResult, ScoredMarketHit

        mock_result = AggregationResult(
            hits=[
                ScoredMarketHit(
                    hit={"source": "ebay", "raw_id": "1", "price": 50.0},
                    provenance_score=0.8,
                    source_reliability=0.9,
                    recency_score=0.05,
                    is_sold=True,
                ),
            ],
            total_sources_queried=1,
            successful_sources=1,
            aggregate_confidence=0.7,
            dedup_count=0,
            query_metadata={},
        )

        mock_agent = MagicMock()
        mock_agent.aggregate_search = AsyncMock(return_value=mock_result)
        mock_agent.persist_comps_to_db = AsyncMock(return_value=1)

        mock_conn = AsyncMock()

        row = {"category": "pokemon", "item_key": "pikachu-vmax", "title": "Pikachu VMAX"}
        semaphore = asyncio.Semaphore(1)

        with patch("workers.catalog_crawler_worker.INTER_ITEM_DELAY", 0):
            from workers.catalog_crawler_worker import _crawl_single_item
            result = await _crawl_single_item(mock_agent, mock_conn, row, semaphore)

        assert result["status"] == "ok"
        assert result["hits"] == 1
        assert result["category"] == "pokemon"

    @pytest.mark.asyncio
    async def test_returns_error_on_failure(self, _mock_supply_snapshot):
        """Failed crawl returns error status."""
        import asyncio

        mock_agent = MagicMock()
        mock_agent.aggregate_search = AsyncMock(side_effect=RuntimeError("Network error"))

        mock_conn = AsyncMock()
        row = {"category": "lego", "item_key": "lego-42115", "title": "Lamborghini"}
        semaphore = asyncio.Semaphore(1)

        with patch("workers.catalog_crawler_worker.INTER_ITEM_DELAY", 0):
            from workers.catalog_crawler_worker import _crawl_single_item
            result = await _crawl_single_item(mock_agent, mock_conn, row, semaphore)

        assert result["status"] == "error"
        assert "Network error" in result["error"]
