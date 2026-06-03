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


def _mock_pool(conn):
    """Wrap a mock connection in a mock asyncpg pool.

    scan_all_active now takes a pool and does `async with pool.acquire() as
    conn` per mandate (D1/D4). This returns a pool whose acquire() yields the
    given mock conn each time.
    """
    pool = MagicMock()

    class _Acq:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    pool.acquire = lambda: _Acq()
    return pool


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
            deals = await agent.scan_all_active(_mock_pool(mock_conn))

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
            [],                # scan_mandate 1: _get_user_recent_deal_urls
            [],                # scan_mandate 2: get_existing_urls
            [],                # scan_mandate 2: _get_user_recent_deal_urls
        ])
        mock_conn.executemany = AsyncMock()  # for _feed_market_hits

        result = _mock_result([_mock_hit(price=200)])

        with patch.object(agent._marketplace, "aggregate_search", new=AsyncMock(return_value=result)):
            with patch.object(agent._marketplace, "close", new=AsyncMock()):
                deals = await agent.scan_all_active(_mock_pool(mock_conn))

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

        # First call is the direct lookup, second is category fallback
        assert mock_conn.fetchrow.await_count >= 1
        # Check the first call (direct lookup) for proper escaping
        first_call = mock_conn.fetchrow.call_args_list[0]

        # The second positional arg is the ILIKE pattern
        ilike_param = first_call[0][1]

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


class TestOutlierFiltering:
    """Tests for DealDiscoveryAgent._filter_outliers (Item 4)."""

    def test_no_outliers_unchanged(self):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        hits = [_mock_hit(price=100), _mock_hit(price=110), _mock_hit(price=105)]
        filtered = DealDiscoveryAgent._filter_outliers(hits)
        assert len(filtered) == 3

    def test_extreme_outlier_removed(self):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        hits = [
            _mock_hit(price=100),
            _mock_hit(price=105),
            _mock_hit(price=110),
            _mock_hit(price=10000),  # extreme outlier
        ]
        filtered = DealDiscoveryAgent._filter_outliers(hits)
        assert len(filtered) == 3
        prices = [float(h.hit["price"]) for h in filtered]
        assert 10000 not in prices

    def test_too_few_hits_not_filtered(self):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        hits = [_mock_hit(price=100), _mock_hit(price=10000)]
        filtered = DealDiscoveryAgent._filter_outliers(hits)
        assert len(filtered) == 2

    def test_all_same_price_not_filtered(self):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        hits = [_mock_hit(price=100), _mock_hit(price=100), _mock_hit(price=100)]
        filtered = DealDiscoveryAgent._filter_outliers(hits)
        assert len(filtered) == 3


class TestCategoryMedianFallback:
    """Tests for category median fallback in _get_prediction (Item 3)."""

    @pytest.mark.asyncio
    async def test_fallback_to_category_median(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        # First fetchrow returns None (no direct match)
        # Second fetchrow returns category median
        mock_conn.fetchrow = AsyncMock(side_effect=[
            None,
            {"cat_q10": 200.0, "cat_q50": 350.0, "cat_q90": 500.0},
        ])

        result = await agent._get_prediction(mock_conn, "nonexistent item", "pokemon")

        assert result is not None
        assert result["q50"] == 350.0
        assert result["q10"] == 200.0
        assert result["q90"] == 500.0

    @pytest.mark.asyncio
    async def test_no_fallback_without_category(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await agent._get_prediction(mock_conn, "test", None)

        assert result is None

    @pytest.mark.asyncio
    async def test_direct_match_skips_fallback(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()

        # Direct match found on first call
        mock_conn.fetchrow = AsyncMock(return_value={
            "q10": 300.0, "q50": 400.0, "q90": 500.0,
        })

        result = await agent._get_prediction(mock_conn, "exact match", "pokemon")

        assert result is not None
        assert result["q50"] == 400.0
        # Only one fetchrow call (no fallback)
        assert mock_conn.fetchrow.await_count == 1


class TestItemLevelCooldown:
    """Tests for _get_user_recent_deal_urls (Item 9: item-level cooldown)."""

    @pytest.mark.asyncio
    async def test_returns_recent_urls(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        user_id = str(uuid.uuid4())

        mock_conn.fetch = AsyncMock(return_value=[
            {"listing_url": "https://ebay.com/itm/1"},
            {"listing_url": "https://ebay.com/itm/2"},
        ])

        urls = await agent._get_user_recent_deal_urls(mock_conn, user_id, cooldown_hours=24)

        assert len(urls) == 2
        assert "https://ebay.com/itm/1" in urls
        assert "https://ebay.com/itm/2" in urls

    @pytest.mark.asyncio
    async def test_empty_when_no_recent_deals(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        user_id = str(uuid.uuid4())
        mock_conn.fetch = AsyncMock(return_value=[])

        urls = await agent._get_user_recent_deal_urls(mock_conn, user_id)
        assert len(urls) == 0

    @pytest.mark.asyncio
    async def test_handles_db_error(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetch = AsyncMock(side_effect=Exception("connection lost"))

        urls = await agent._get_user_recent_deal_urls(mock_conn, "invalid-id")
        assert len(urls) == 0  # Returns empty set on error


class TestFeedMarketHits:
    """Tests for _feed_market_hits (Item 13: feed discoveries into market_hits)."""

    @pytest.mark.asyncio
    async def test_feeds_valid_hits(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.executemany = AsyncMock()

        hits = [
            _mock_hit(price=100, url="https://ebay.com/itm/1", title="Item A"),
            _mock_hit(price=200, url="https://ebay.com/itm/2", title="Item B"),
        ]

        await agent._feed_market_hits(mock_conn, hits, "Charizard PSA 10", "pokemon")

        mock_conn.executemany.assert_awaited_once()
        call_args = mock_conn.executemany.call_args
        sql = call_args[0][0]
        assert "INSERT INTO public.market_hits" in sql
        assert "ON CONFLICT" in sql
        rows = call_args[0][1]
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_skips_zero_price_hits(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.executemany = AsyncMock()

        hits = [
            _mock_hit(price=0, url="https://ebay.com/itm/1"),
            _mock_hit(price=100, url="https://ebay.com/itm/2"),
        ]

        await agent._feed_market_hits(mock_conn, hits, "test", "pokemon")

        call_args = mock_conn.executemany.call_args
        rows = call_args[0][1]
        assert len(rows) == 1  # Only the non-zero price hit

    @pytest.mark.asyncio
    async def test_handles_db_error_gracefully(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.executemany = AsyncMock(side_effect=Exception("constraint error"))

        hits = [_mock_hit(price=100)]

        # Should not raise
        await agent._feed_market_hits(mock_conn, hits, "test", "pokemon")


class TestBoundedScan:
    """Tests that scan_all_active passes a LIMIT parameter."""

    @pytest.mark.asyncio
    async def test_scan_all_active_has_limit(self, mock_conn):
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch.object(agent._marketplace, "close", new=AsyncMock()):
            await agent.scan_all_active(_mock_pool(mock_conn))

        mock_conn.fetch.assert_awaited_once()
        call_args = mock_conn.fetch.call_args

        # The SQL query should contain LIMIT
        sql = call_args[0][0]
        assert "LIMIT" in sql

        # The limit parameter should be MAX_MANDATES_PER_CYCLE (50)
        limit_param = call_args[0][1]
        assert limit_param == DealDiscoveryAgent.MAX_MANDATES_PER_CYCLE
        assert limit_param == 50


class TestImageCaching:
    """Tests for _cache_deal_images in DealDiscoveryAgent (Item 14)."""

    @pytest.mark.asyncio
    async def test_cache_images_skips_when_no_s3(self, mock_conn):
        """When S3ImageCache is not enabled, no DB updates happen."""
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        deal_id = uuid.uuid4()
        batch_rows = [
            (deal_id, uuid.uuid4(), uuid.uuid4(), "ebay", "https://ebay.com/1",
             "https://ebay.com/1", "Test Item", 100.0, "EUR", "NM",
             "https://i.ebayimg.com/images/g/xyz.jpg", "seller1",
             0.8, 0.75, -15.0, 90.0, 80.0, 100.0, True, '["ok"]', "ebay"),
        ]

        mock_cache_instance = MagicMock()
        mock_cache_instance.enabled = False

        mock_cache_module = MagicMock()
        mock_cache_module.S3ImageCache.return_value = mock_cache_instance

        with patch.dict("sys.modules", {"pipelines.s3_image_cache": mock_cache_module}):
            await agent._cache_deal_images(mock_conn, batch_rows, "pokemon")
            mock_cache_instance.close.assert_called_once()
            # No executemany called since cache is disabled
            mock_conn.executemany.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_images_updates_db_on_success(self, mock_conn):
        """When S3 caching succeeds, listing_image_url is updated in DB."""
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        deal_id = uuid.uuid4()
        orig_url = "https://i.ebayimg.com/images/g/xyz.jpg"
        cached_url = "https://d1234.cloudfront.net/catalog-images/pokemon/test.jpg"

        batch_rows = [
            (deal_id, uuid.uuid4(), uuid.uuid4(), "ebay", "https://ebay.com/1",
             "https://ebay.com/1", "Test Item", 100.0, "EUR", "NM",
             orig_url, "seller1",
             0.8, 0.75, -15.0, 90.0, 80.0, 100.0, True, '["ok"]', "ebay"),
        ]

        mock_cache_instance = MagicMock()
        mock_cache_instance.enabled = True
        mock_cache_instance.cache_batch.return_value = {orig_url: cached_url}

        mock_cache_module = MagicMock()
        mock_cache_module.S3ImageCache.return_value = mock_cache_instance

        mock_conn.executemany = AsyncMock()

        import asyncio
        with patch.dict("sys.modules", {"pipelines.s3_image_cache": mock_cache_module}):
            await agent._cache_deal_images(mock_conn, batch_rows, "pokemon")

        # DB should be updated with cached URL
        mock_conn.executemany.assert_awaited_once()
        update_args = mock_conn.executemany.call_args[0]
        assert "listing_image_url" in update_args[0]
        assert update_args[1][0][1] == cached_url

    @pytest.mark.asyncio
    async def test_cache_images_skips_rows_without_image(self, mock_conn):
        """Rows with no image_url are skipped."""
        from app.agents.deal_discovery_agent import DealDiscoveryAgent

        agent = DealDiscoveryAgent()
        deal_id = uuid.uuid4()

        # image_url (index 10) is None
        batch_rows = [
            (deal_id, uuid.uuid4(), uuid.uuid4(), "ebay", "https://ebay.com/1",
             "https://ebay.com/1", "Test Item", 100.0, "EUR", "NM",
             None, "seller1",
             0.8, 0.75, -15.0, 90.0, 80.0, 100.0, True, '["ok"]', "ebay"),
        ]

        mock_cache_instance = MagicMock()
        mock_cache_instance.enabled = True

        mock_cache_module = MagicMock()
        mock_cache_module.S3ImageCache.return_value = mock_cache_instance

        with patch.dict("sys.modules", {"pipelines.s3_image_cache": mock_cache_module}):
            await agent._cache_deal_images(mock_conn, batch_rows, "pokemon")

        # cache_batch should not be called since no images to cache
        mock_cache_instance.cache_batch.assert_not_called()
        mock_cache_instance.close.assert_called_once()
