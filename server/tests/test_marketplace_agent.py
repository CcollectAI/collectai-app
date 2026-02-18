"""
Tests for app/agents/marketplace_agent.py — MarketplaceAgent.

Covers:
  - Helper functions: _content_hash, _parse_sold_date, _compute_recency_score,
    _compute_provenance_score, _compute_aggregate_confidence
  - ScoredMarketHit / AggregationResult serialization
  - MarketplaceAgent.aggregate_search() with mocked adapters
  - Deduplication logic
  - Provenance scoring
  - No-adapters edge case
  - Error handling when adapters raise exceptions
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestContentHash:
    """Tests for _content_hash()."""

    def test_deterministic(self):
        from app.agents.marketplace_agent import _content_hash

        h1 = _content_hash("ebay", "item-123")
        h2 = _content_hash("ebay", "item-123")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256

    def test_different_inputs_different_hash(self):
        from app.agents.marketplace_agent import _content_hash

        h1 = _content_hash("ebay", "item-123")
        h2 = _content_hash("ebay", "item-456")
        assert h1 != h2

    def test_different_sources_different_hash(self):
        from app.agents.marketplace_agent import _content_hash

        h1 = _content_hash("ebay", "item-123")
        h2 = _content_hash("tcgplayer", "item-123")
        assert h1 != h2


class TestParseSoldDate:
    """Tests for _parse_sold_date()."""

    def test_iso_with_fractional_seconds(self):
        from app.agents.marketplace_agent import _parse_sold_date

        dt = _parse_sold_date("2026-01-15T10:30:00.000Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1

    def test_iso_without_fractional(self):
        from app.agents.marketplace_agent import _parse_sold_date

        dt = _parse_sold_date("2026-02-01T08:00:00Z")
        assert dt is not None
        assert dt.day == 1

    def test_date_only(self):
        from app.agents.marketplace_agent import _parse_sold_date

        dt = _parse_sold_date("2026-01-20")
        assert dt is not None
        assert dt.day == 20

    def test_none_input(self):
        from app.agents.marketplace_agent import _parse_sold_date

        assert _parse_sold_date(None) is None

    def test_empty_string(self):
        from app.agents.marketplace_agent import _parse_sold_date

        assert _parse_sold_date("") is None

    def test_unparseable_string(self):
        from app.agents.marketplace_agent import _parse_sold_date

        assert _parse_sold_date("not-a-date") is None


class TestComputeRecencyScore:
    """Tests for _compute_recency_score()."""

    def test_recent_7d_boost(self):
        from app.agents.marketplace_agent import _compute_recency_score, RECENCY_7D_BOOST

        # 2 days ago
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        score = _compute_recency_score(recent)
        assert score == RECENCY_7D_BOOST

    def test_recent_30d_boost(self):
        from app.agents.marketplace_agent import _compute_recency_score, RECENCY_30D_BOOST

        # 15 days ago
        recent = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        score = _compute_recency_score(recent)
        assert score == RECENCY_30D_BOOST

    def test_old_date_no_boost(self):
        from app.agents.marketplace_agent import _compute_recency_score

        old = "2020-01-01T00:00:00Z"
        assert _compute_recency_score(old) == 0.0

    def test_none_returns_zero(self):
        from app.agents.marketplace_agent import _compute_recency_score

        assert _compute_recency_score(None) == 0.0


class TestComputeProvenanceScore:
    """Tests for _compute_provenance_score()."""

    def test_ebay_sold_high_reliability(self):
        from app.agents.marketplace_agent import _compute_provenance_score, SOURCE_RELIABILITY, SOLD_BONUS

        hit = {"source": "ebay", "is_sold": True}
        prov, reliability, recency, is_sold = _compute_provenance_score(hit)
        assert reliability == SOURCE_RELIABILITY["ebay_sold"]
        assert is_sold is True
        # Score should include sold bonus
        assert prov >= reliability

    def test_ebay_listed_lower_reliability(self):
        from app.agents.marketplace_agent import _compute_provenance_score, SOURCE_RELIABILITY

        hit = {"source": "ebay", "is_sold": False}
        prov, reliability, recency, is_sold = _compute_provenance_score(hit)
        assert reliability == SOURCE_RELIABILITY["ebay_listed"]
        assert is_sold is False

    def test_condition_match_bonus(self):
        from app.agents.marketplace_agent import _compute_provenance_score, CONDITION_MATCH_BONUS

        hit = {"source": "ebay", "is_sold": False, "condition": "Near Mint"}
        prov_match, _, _, _ = _compute_provenance_score(hit, query_condition="near mint")
        prov_no_match, _, _, _ = _compute_provenance_score(hit, query_condition="damaged")
        assert prov_match > prov_no_match

    def test_unknown_source_default_reliability(self):
        from app.agents.marketplace_agent import _compute_provenance_score

        hit = {"source": "unknown_source", "is_sold": False}
        prov, reliability, recency, is_sold = _compute_provenance_score(hit)
        assert reliability == 0.50  # default

    def test_provenance_score_capped_at_one(self):
        from app.agents.marketplace_agent import _compute_provenance_score

        # Create a hit that should max out the score
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hit = {
            "source": "ebay",
            "is_sold": True,
            "sold_at": recent,
            "condition": "Mint",
        }
        prov, _, _, _ = _compute_provenance_score(hit, query_condition="Mint")
        assert prov <= 1.0


class TestComputeAggregateConfidence:
    """Tests for _compute_aggregate_confidence()."""

    def test_empty_hits_returns_zero(self):
        from app.agents.marketplace_agent import _compute_aggregate_confidence

        assert _compute_aggregate_confidence([], 3, 0) == 0.0

    def test_zero_total_sources_returns_zero(self):
        from app.agents.marketplace_agent import _compute_aggregate_confidence

        assert _compute_aggregate_confidence([], 0, 0) == 0.0

    def test_higher_with_more_hits(self):
        from app.agents.marketplace_agent import (
            _compute_aggregate_confidence,
            ScoredMarketHit,
        )

        def _make_hits(n):
            return [
                ScoredMarketHit(
                    hit={"source": "ebay", "raw_id": str(i)},
                    provenance_score=0.8,
                    source_reliability=0.9,
                    recency_score=0.05,
                    is_sold=True,
                )
                for i in range(n)
            ]

        conf_5 = _compute_aggregate_confidence(_make_hits(5), 3, 3)
        conf_15 = _compute_aggregate_confidence(_make_hits(15), 3, 3)
        assert conf_15 > conf_5

    def test_capped_at_one(self):
        from app.agents.marketplace_agent import (
            _compute_aggregate_confidence,
            ScoredMarketHit,
        )

        hits = [
            ScoredMarketHit(
                hit={}, provenance_score=1.0, source_reliability=1.0,
                recency_score=0.1, is_sold=True,
            )
            for _ in range(50)
        ]
        conf = _compute_aggregate_confidence(hits, 4, 4)
        assert conf <= 1.0


# ---------------------------------------------------------------------------
# Data class serialization
# ---------------------------------------------------------------------------


class TestDataClassSerialization:
    """Tests for ScoredMarketHit and AggregationResult to_dict()."""

    def test_scored_market_hit_to_dict(self):
        from app.agents.marketplace_agent import ScoredMarketHit

        hit = ScoredMarketHit(
            hit={"source": "ebay", "title": "Test"},
            provenance_score=0.856789,
            source_reliability=0.95,
            recency_score=0.10,
            is_sold=True,
        )
        d = hit.to_dict()
        assert d["provenance_score"] == 0.8568
        assert d["source_reliability"] == 0.95
        assert d["is_sold"] is True

    def test_aggregation_result_to_dict(self):
        from app.agents.marketplace_agent import AggregationResult, ScoredMarketHit

        result = AggregationResult(
            hits=[
                ScoredMarketHit(
                    hit={"source": "ebay", "raw_id": "1"},
                    provenance_score=0.9,
                    source_reliability=0.95,
                    recency_score=0.1,
                    is_sold=True,
                )
            ],
            total_sources_queried=3,
            successful_sources=2,
            aggregate_confidence=0.75,
            dedup_count=1,
            query_metadata={"query": "test"},
        )
        d = result.to_dict()
        assert len(d["hits"]) == 1
        assert d["total_sources_queried"] == 3
        assert d["aggregate_confidence"] == 0.75
        assert d["dedup_count"] == 1


# ---------------------------------------------------------------------------
# MarketplaceAgent.aggregate_search — mocked adapters
# ---------------------------------------------------------------------------


class TestMarketplaceAgentSearch:
    """Tests for MarketplaceAgent.aggregate_search() with mocked adapters."""

    @pytest.mark.asyncio
    async def test_no_adapters_configured(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = False
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = False
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            result = await agent.aggregate_search("Charizard")

        assert result.total_sources_queried == 0
        assert len(result.hits) == 0
        assert result.aggregate_confidence == 0.0

    @pytest.mark.asyncio
    async def test_search_with_single_adapter(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        mock_ebay_hits = [
            {"source": "ebay", "raw_id": "eb-1", "title": "Charizard V", "price": 50.0,
             "currency": "EUR", "is_sold": False, "condition": "Near Mint"},
            {"source": "ebay", "raw_id": "eb-2", "title": "Charizard VMAX", "price": 80.0,
             "currency": "EUR", "is_sold": False, "condition": "Mint"},
        ]

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = True
            agent._ebay.search = AsyncMock(return_value=mock_ebay_hits)
            agent._ebay.sold_comps = AsyncMock(return_value=[])
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = False
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            result = await agent.aggregate_search("Charizard")

        assert len(result.hits) == 2
        assert result.successful_sources >= 1
        # Hits should be sorted by provenance score descending
        scores = [h.provenance_score for h in result.hits]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_dedup_removes_duplicate_hits(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        # Same source + raw_id means duplicate
        dup_hit = {"source": "ebay", "raw_id": "eb-same", "title": "Charizard",
                   "price": 50.0, "currency": "EUR", "is_sold": False}

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = True
            agent._ebay.search = AsyncMock(return_value=[dup_hit.copy()])
            agent._ebay.sold_comps = AsyncMock(return_value=[dup_hit.copy()])
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = False
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            result = await agent.aggregate_search("Charizard")

        assert result.dedup_count == 1
        assert len(result.hits) == 1

    @pytest.mark.asyncio
    async def test_adapter_exception_does_not_crash(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = True
            agent._ebay.search = AsyncMock(side_effect=RuntimeError("API down"))
            agent._ebay.sold_comps = AsyncMock(side_effect=RuntimeError("API down"))
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = False
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            result = await agent.aggregate_search("test")

        # Should succeed with empty results, not raise
        assert len(result.hits) == 0
        assert "ebay_listed" in result.query_metadata.get("source_errors", [])

    @pytest.mark.asyncio
    async def test_tcgplayer_only_for_tcg_categories(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = False
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = True
            agent._tcgplayer.search = AsyncMock(return_value=[])
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            # Non-TCG category should skip TCGPlayer
            result = await agent.aggregate_search("LEGO Star Wars", category="lego")

        assert result.total_sources_queried == 0
        agent._tcgplayer.search.assert_not_called()


# ---------------------------------------------------------------------------
# MarketplaceAgent.find_sold_comps
# ---------------------------------------------------------------------------


class TestMarketplaceAgentSoldComps:
    """Tests for MarketplaceAgent.find_sold_comps()."""

    @pytest.mark.asyncio
    async def test_sold_comps_basic(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        mock_sold = [
            {"source": "ebay", "raw_id": "sold-1", "title": "Pokemon Card",
             "price": 100.0, "currency": "EUR", "is_sold": True,
             "sold_at": "2026-02-01T00:00:00Z"},
        ]

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = True
            agent._ebay.sold_comps = AsyncMock(return_value=mock_sold)
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = False
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            result = await agent.find_sold_comps("Pokemon Card", category="pokemon")

        assert len(result.hits) == 1
        assert result.hits[0].is_sold is True
        assert result.query_metadata["mode"] == "sold_comps"


# ---------------------------------------------------------------------------
# MarketplaceAgent.health_check
# ---------------------------------------------------------------------------


class TestMarketplaceAgentHealth:
    """Tests for MarketplaceAgent.health_check()."""

    @pytest.mark.asyncio
    async def test_all_unconfigured(self):
        from app.agents.marketplace_agent import MarketplaceAgent

        with patch.object(MarketplaceAgent, "__init__", lambda self: None):
            agent = MarketplaceAgent()
            agent._ebay = MagicMock()
            agent._ebay.configured = False
            agent._tcgplayer = MagicMock()
            agent._tcgplayer.configured = False
            agent._firecrawl = MagicMock()
            agent._firecrawl.configured = False
            agent._crawl4ai = MagicMock()
            agent._crawl4ai.configured = False

            health = await agent.health_check()

        assert health["any_healthy"] is False
        assert health["adapters"]["ebay"]["configured"] is False
