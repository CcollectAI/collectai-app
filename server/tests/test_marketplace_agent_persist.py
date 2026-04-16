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

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.get_conn", return_value=mock_ctx), \
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

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.get_conn", return_value=mock_ctx), \
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

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.get_conn", return_value=mock_ctx), \
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

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.db.get_conn", return_value=mock_ctx), \
             patch("app.db.db_configured", return_value=True):
            agent = MarketplaceAgent()
            # Must not raise TypeError for unexpected kwarg
            count = await agent.persist_comps_to_db(result, normalized_key="pokemon:pika", category="pokemon")

        assert count == 1
