"""
Tests for app/agents/deal_discovery_agent.py — DealDiscoveryAgent.

Covers:
  - scan_mandate with mocked MarketplaceAgent
  - Policy engine integration (passing/failing hits)
  - Deduplication against existing deals
  - Mandate counter updates
  - scan_all_active with no mandates
  - Error resilience when marketplace fails
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.agents.marketplace_agent import ScoredMarketHit, AggregationResult


def _mock_hit(price=350, source="ebay", url="https://ebay.com/itm/1", title="Test Item"):
    return ScoredMarketHit(
        hit={
            "price": price,
            "source": source,
            "url": url,
            "title": title,
            "currency": "EUR",
            "condition": "Near Mint",
            "raw_id": str(uuid.uuid4()),
        },
        provenance_score=0.85,
        source_reliability=0.90,
        recency_score=0.10,
        is_sold=False,
    )


def _mock_result(hits=None):
    if hits is None:
        hits = [_mock_hit()]
    return AggregationResult(
        hits=hits,
        total_sources_queried=3,
        successful_sources=2,
        aggregate_confidence=0.75,
        dedup_count=0,
        query_metadata={"query": "test"},
    )


def _mandate(**overrides):
    m = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "search_query": "Charizard PSA 10",
        "category": "pokemon",
        "region": "europe",
        "max_price": 500.0,
        "max_total_budget": None,
        "spent_total": 0.0,
        "min_trust_score": 0.60,
        "cooldown_hours": 24,
        "allowed_sources": [],
        "expires_at": None,
        "last_deal_at": None,
        "status": "active",
    }
    m.update(overrides)
    return m


@pytest.fixture
def mock_conn():
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    return conn


class TestScanMandate:
    @pytest.mark.asyncio
    async def test_returns_new_deals_for_passing_hits(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        result = _mock_result([_mock_hit(price=300)])

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(return_value=result)):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_mandate(_mandate(max_price=500), mock_conn)

        assert len(deals) == 1
        assert deals[0]["listing_price"] == 300

    @pytest.mark.asyncio
    async def test_no_deals_when_all_fail_policy(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        # Price exceeds max_price
        result = _mock_result([_mock_hit(price=999)])

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(return_value=result)):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_mandate(_mandate(max_price=100), mock_conn)

        assert len(deals) == 0

    @pytest.mark.asyncio
    async def test_deduplication_skips_existing_urls(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        existing_url = "https://ebay.com/itm/existing"
        mock_conn.fetch = AsyncMock(return_value=[{"listing_url": existing_url}])

        result = _mock_result([_mock_hit(url=existing_url)])

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(return_value=result)):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_mandate(_mandate(), mock_conn)

        assert len(deals) == 0

    @pytest.mark.asyncio
    async def test_empty_search_results(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        result = _mock_result([])

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(return_value=result)):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_mandate(_mandate(), mock_conn)

        assert len(deals) == 0

    @pytest.mark.asyncio
    async def test_marketplace_error_returns_empty(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(side_effect=Exception("API down"))):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_mandate(_mandate(), mock_conn)

        assert len(deals) == 0


class TestScanAllActive:
    @pytest.mark.asyncio
    async def test_no_active_mandates(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch.object(agent._marketplace, "close", new=AsyncMock()):
            deals = await agent.scan_all_active(mock_conn)

        assert len(deals) == 0

    @pytest.mark.asyncio
    async def test_processes_multiple_mandates(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        # Two mandates
        mandates = [_mandate(), _mandate()]
        mock_conn.fetch = AsyncMock(side_effect=[
            mandates,          # first call: scan_all_active fetches mandates
            [],                # scan_mandate 1: get_existing_urls
            [],                # scan_mandate 2: get_existing_urls
        ])

        result = _mock_result([_mock_hit(price=200)])

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(return_value=result)):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_all_active(mock_conn)

        assert len(deals) == 2


class TestGetPrediction:
    """Tests for DealDiscoveryAgent._get_prediction (wildcard escaping, DB lookup)."""

    @pytest.mark.asyncio
    async def test_prediction_found(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        mock_conn.fetchrow = AsyncMock(return_value={
            "q10": 300.0,
            "q50": 400.0,
            "q90": 500.0,
        })

        result = await agent._get_prediction(mock_conn, "test query", "pokemon")

        assert result is not None
        assert result["q10"] == 300.0
        assert result["q50"] == 400.0
        assert result["q90"] == 500.0

    @pytest.mark.asyncio
    async def test_prediction_not_found(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await agent._get_prediction(mock_conn, "nonexistent card", "pokemon")

        assert result is None

    @pytest.mark.asyncio
    async def test_prediction_db_error(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("connection lost"))

        result = await agent._get_prediction(mock_conn, "test query", "pokemon")

        assert result is None

    @pytest.mark.asyncio
    async def test_prediction_escapes_wildcards(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        mock_conn.fetchrow = AsyncMock(return_value=None)

        # Query containing ILIKE wildcards that must be escaped
        await agent._get_prediction(mock_conn, "100% mint_condition\\special", "pokemon")

        # Verify fetchrow was called
        mock_conn.fetchrow.assert_awaited_once()
        call_args = mock_conn.fetchrow.call_args

        # The second positional arg is the ILIKE pattern
        ilike_param = call_args[0][1]

        # The literal %, _, and \ from the query must be escaped
        assert "\\%" in ilike_param, f"Expected escaped % in {ilike_param!r}"
        assert "\\_" in ilike_param, f"Expected escaped _ in {ilike_param!r}"
        assert "\\\\" in ilike_param, f"Expected escaped backslash in {ilike_param!r}"

        # The outer wrapping % for ILIKE should still be present
        assert ilike_param.startswith("%")
        assert ilike_param.endswith("%")


class TestPersistDealsBatch:
    """Tests for DealDiscoveryAgent._persist_deals_batch (executemany)."""

    @pytest.mark.asyncio
    async def test_batch_persist_calls_executemany(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        mock_conn.executemany = AsyncMock()

        rows = [
            (
                uuid.uuid4(),        # deal id
                uuid.uuid4(),        # mandate id
                uuid.uuid4(),        # user id
                "ebay",              # listing_source
                "https://ebay.com/1",  # listing_url
                "https://aff.link/1",  # affiliate_url
                "Test Item",         # listing_title
                350.0,               # listing_price
                "EUR",               # listing_currency
                "Near Mint",         # listing_condition
                None,                # listing_image_url
                None,                # listing_seller
                0.85,                # provenance_score
                0.72,                # deal_score
                -15.0,               # price_vs_q50_pct
                400.0,               # predicted_q50
                300.0,               # predicted_q10
                500.0,               # predicted_q90
                True,                # policy_passed
                '["price below max"]',  # policy_reasons (jsonb)
                "ebay_partner",      # affiliate_source
            ),
        ]

        await agent._persist_deals_batch(mock_conn, rows)

        mock_conn.executemany.assert_awaited_once()
        call_args = mock_conn.executemany.call_args
        sql = call_args[0][0]
        assert "INSERT INTO public.mandate_deals" in sql
        assert call_args[0][1] is rows

    @pytest.mark.asyncio
    async def test_batch_persist_handles_error(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        mock_conn.executemany = AsyncMock(
            side_effect=Exception("unique constraint violation")
        )

        rows = [
            (
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
                "ebay", "https://ebay.com/1", "",
                "Item", 100.0, "EUR",
                None, None, None,
                0.8, 0.5, 0.0,
                None, None, None,
                False, "[]",
                None,
            ),
        ]

        # Should not raise — error is caught internally
        await agent._persist_deals_batch(mock_conn, rows)


class TestBoundedScan:
    """Tests that scan_all_active passes a LIMIT parameter."""

    @pytest.mark.asyncio
    async def test_scan_all_active_has_limit(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch.object(agent._marketplace, "close", new=AsyncMock()):
            await agent.scan_all_active(mock_conn)

        mock_conn.fetch.assert_awaited_once()
        call_args = mock_conn.fetch.call_args

        # The SQL query should contain LIMIT
        sql = call_args[0][0]
        assert "LIMIT" in sql

        # The limit parameter should be MAX_MANDATES_PER_CYCLE (50)
        limit_param = call_args[0][1]
        assert limit_param == DealDiscoveryAgent.MAX_MANDATES_PER_CYCLE
        assert limit_param == 50
