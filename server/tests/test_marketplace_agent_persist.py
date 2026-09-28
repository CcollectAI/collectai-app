"""
Tests for MarketplaceAgent.persist_comps_to_db — attribute persistence.

Verifies that the INSERT includes attrs JSONB column and handles edge cases.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


def _mock_direct_conn() -> "AsyncMock":
    """A stand-in for the connection persist_comps_to_db actually opens.

    These tests used to patch `app.db.get_conn`. That stopped being the seam on
    2026-04-27, when persist_comps_to_db moved to its own
    `asyncpg.connect(DB_DSN_DIRECT)` to escape the pooler's 30s statement cap
    (marketplace_agent.py:660). The patch then applied to a function no longer
    in the path, the real connect ran, and every one of these failed with
    `Connect call failed ('127.0.0.1', 5432)` -- a test pinning an architecture
    the code had left behind. `import asyncpg as _asyncpg` inside the function
    still resolves the shared module object, so patching `asyncpg.connect`
    reaches it.
    """
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    return conn


def _make_result(hits_data: list[dict]) -> "AggregationResult":
    """Build an AggregationResult from simplified hit dicts."""
    from app.agents.marketplace_agent import ScoredMarketHit, AggregationResult
    scored = []
    for h in hits_data:
        scored.append(ScoredMarketHit(
            hit=h,
            provenance_score=0.8,
            source_reliability=0.7,
            recency_score=0.9,
            is_sold=False,
        ))
    return AggregationResult(
        hits=scored,
        total_sources_queried=1,
        successful_sources=1,
        aggregate_confidence=0.75,
        dedup_count=0,
        query_metadata={"query": "test"},
    )


class TestPersistCompsAttrs:

    @pytest.mark.asyncio
    async def test_attrs_included_in_insert(self):
        """persist_comps_to_db should pass attrs as the last INSERT param."""
        from app.agents.marketplace_agent import MarketplaceAgent

        hit = {
            "source": "ebay",
            "raw_id": "ebay-123",
            "title": "Test Card",
            "price": 50.0,
            "currency": "EUR",
            "url": "https://ebay.com/123",
            "condition": "Used",
            "attributes": {"brand": "WOTC", "year": "1999"},
        }
        result = _make_result([hit])

        mock_conn = _mock_direct_conn()

        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            agent = MarketplaceAgent()
            count = await agent.persist_comps_to_db(result, normalized_key="pokemon:charizard")

        assert count == 1
        call_args = mock_conn.execute.call_args
        # The last positional arg should be the JSON-serialized attrs
        attrs_json = call_args[0][-1]
        parsed = json.loads(attrs_json)
        assert parsed["brand"] == "WOTC"
        assert parsed["year"] == "1999"

    @pytest.mark.asyncio
    async def test_empty_attrs_gives_empty_json(self):
        """When hit has no attributes, persist should store '{}'."""
        from app.agents.marketplace_agent import MarketplaceAgent

        hit = {
            "source": "crawl4ai",
            "raw_id": "c4-999",
            "title": "Generic Item",
            "price": 10.0,
            "currency": "EUR",
            "url": "https://example.com/999",
        }
        result = _make_result([hit])

        mock_conn = _mock_direct_conn()

        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            agent = MarketplaceAgent()
            count = await agent.persist_comps_to_db(result)

        assert count == 1
        attrs_json = mock_conn.execute.call_args[0][-1]
        assert json.loads(attrs_json) == {}

    @pytest.mark.asyncio
    async def test_zero_price_skipped(self):
        """Hits with 0 price should not be inserted."""
        from app.agents.marketplace_agent import MarketplaceAgent

        hit = {
            "source": "vinted",
            "raw_id": "v-0",
            "title": "Free Item",
            "price": 0,
            "currency": "EUR",
            "attributes": {"brand": "Test"},
        }
        result = _make_result([hit])

        mock_conn = _mock_direct_conn()

        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            agent = MarketplaceAgent()
            count = await agent.persist_comps_to_db(result)

        assert count == 0
        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_category_param_accepted(self):
        """persist_comps_to_db should accept category kwarg without error."""
        from app.agents.marketplace_agent import MarketplaceAgent

        hit = {
            "source": "mercari_us",
            "raw_id": "m-1",
            "title": "Card",
            "price": 25.0,
            "currency": "USD",
            "attributes": {"condition": "Like New"},
        }
        result = _make_result([hit])

        mock_conn = _mock_direct_conn()

        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            agent = MarketplaceAgent()
            # Must not raise TypeError for unexpected kwarg
            count = await agent.persist_comps_to_db(result, normalized_key="pokemon:pika", category="pokemon")

        assert count == 1


class TestPersistCountsWhatPostgresInserted:
    """2026-09-27: `inserted += 1` ran even when WHERE NOT EXISTS dropped the
    row, so "Persisted N/N" held while nothing was written."""

    async def _persist(self, status):
        from app.agents.marketplace_agent import MarketplaceAgent
        hit = {"source": "ebay", "raw_id": "ebay-123", "title": "Test Card",
               "price": 50.0, "currency": "EUR", "url": "https://ebay.com/123"}
        mock_conn = _mock_direct_conn()
        mock_conn.execute = AsyncMock(return_value=status)
        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            return await MarketplaceAgent().persist_comps_to_db(
                _make_result([hit]), normalized_key="pokemon:charizard")

    @pytest.mark.asyncio
    async def test_a_dropped_repeat_counts_zero(self):
        assert await self._persist("INSERT 0 0") == 0

    @pytest.mark.asyncio
    async def test_a_real_insert_counts_one(self):
        assert await self._persist("INSERT 0 1") == 1


def test_discogs_adapter_release_key_is_dated():
    """A release's asking price is a series; `discogs-<id>` kept only the first."""
    from datetime import datetime, timezone
    from app.agents.adapters import discogs_caller as dc
    import inspect
    fn = next(f for n, f in inspect.getmembers(dc, inspect.isfunction)
              if '"raw_id": f"discogs-{item.get' in inspect.getsource(f))
    hit = fn({"id": 42, "title": "A - B", "lowest_price": 9.5})
    assert hit["raw_id"] == f"discogs-42-{datetime.now(timezone.utc).date().isoformat()}"


class TestUndatedScraperSold:
    """OPEN_DECISIONS #15: a scraper's undated 'sold' row is not stored."""

    @pytest.mark.asyncio
    async def test_scraper_sold_row_without_date_is_skipped(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        sold = {"source": "crawl4ai", "raw_id": "c-1", "title": "Space Marine box sold",
                "price": 30.0, "currency": "EUR", "url": "https://thetrolltrader.com/p/1",
                "is_sold": True, "sold_at": None}
        live = {**sold, "raw_id": "c-2", "title": "Space Marine box", "is_sold": False}
        mock_conn = _mock_direct_conn()
        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            count = await MarketplaceAgent().persist_comps_to_db(
                _make_result([sold, live]), normalized_key="warhammer:x")
        assert count == 1

    @pytest.mark.asyncio
    async def test_trusted_source_sold_row_is_kept(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        sold = {"source": "ebay", "raw_id": "e-1", "title": "Charizard base set",
                "price": 300.0, "currency": "EUR", "url": "https://www.ebay.com/itm/1",
                "is_sold": True, "sold_at": None}
        mock_conn = _mock_direct_conn()
        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.db.db_configured", return_value=True):
            count = await MarketplaceAgent().persist_comps_to_db(
                _make_result([sold]), normalized_key="pokemon:x")
        assert count == 1


def test_scraper_set_matches_the_markdown_scrapers():
    import pathlib, re
    from app.agents.marketplace_agent import _UNDATED_SOLD_SCRAPERS

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "agents" / "adapters"
    derived = {"firecrawl"}
    for p in root.glob("*_caller.py"):
        src = p.read_text()
        if "_extract_url_from_listing" in src and p.name != "firecrawl_caller.py":
            derived |= set(re.findall(r'"source": "([a-z0-9_]+)"', src))
    assert derived == set(_UNDATED_SOLD_SCRAPERS)
