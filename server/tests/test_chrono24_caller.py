"""
Tests for app/agents/adapters/chrono24_caller.py — Chrono24 watch marketplace adapter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from workers.circuit_breaker import chrono24_circuit


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeListing:
    """Tests for _normalize_listing()."""

    def test_basic_normalization(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {
            "id": "12345",
            "manufacturer": "Rolex",
            "model": "Submariner",
            "referenceNumber": "126610LN",
            "price": 15000.00,
            "currency": "EUR",
            "imageUrl": "https://img.chrono24.com/sub.jpg",
            "condition": "Very Good",
        }
        hit = _normalize_listing(item)
        assert hit["source"] == "chrono24"
        assert hit["raw_id"] == "chrono24-12345"
        assert "Rolex" in hit["title"]
        assert "Submariner" in hit["title"]
        assert "126610LN" in hit["title"]
        assert hit["price"] == 15000.00
        assert hit["currency"] == "EUR"
        assert hit["image_url"] == "https://img.chrono24.com/sub.jpg"
        assert hit["condition"] == "Very Good"
        assert hit["is_sold"] is False

    def test_sold_listing(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {
            "id": "sold789",
            "manufacturer": "Omega",
            "model": "Speedmaster",
            "price": 6500,
            "currency": "EUR",
            "soldAt": "2026-01-20T08:00:00Z",
        }
        hit = _normalize_listing(item, is_sold=True)
        assert hit["is_sold"] is True
        assert hit["sold_at"] == "2026-01-20T08:00:00Z"

    def test_nested_price_object(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {
            "id": "nested1",
            "title": "Tag Heuer Monaco",
            "price": {"value": 4800, "currency": "USD"},
        }
        hit = _normalize_listing(item)
        assert hit["price"] == 4800.0
        assert hit["currency"] == "USD"

    def test_brand_fallback(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "bf1", "brand": "Seiko", "model": "Presage"}
        hit = _normalize_listing(item)
        assert "Seiko" in hit["title"]
        assert "Presage" in hit["title"]

    def test_title_fallback(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "tf1", "title": "Custom Watch Title"}
        hit = _normalize_listing(item)
        assert hit["title"] == "Custom Watch Title"

    def test_empty_item(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        hit = _normalize_listing({})
        assert hit["source"] == "chrono24"
        assert hit["raw_id"] == "chrono24-"
        assert hit["price"] == 0.0
        assert hit["currency"] == "EUR"

    def test_url_from_slug_absolute(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "u1", "url": "https://www.chrono24.com/rolex/sub--id12345.htm"}
        hit = _normalize_listing(item)
        assert hit["url"] == "https://www.chrono24.com/rolex/sub--id12345.htm"

    def test_url_from_slug_relative(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "u2", "slug": "/rolex/sub--id12345.htm"}
        hit = _normalize_listing(item)
        assert hit["url"] == "https://www.chrono24.com/rolex/sub--id12345.htm"

    def test_url_from_id(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "99999"}
        hit = _normalize_listing(item)
        assert hit["url"] == "https://www.chrono24.com/id99999.htm"

    def test_condition_dict(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "c1", "condition": {"label": "New with tags", "name": "NWT"}}
        hit = _normalize_listing(item)
        assert hit["condition"] == "New with tags"

    def test_image_from_image_dict(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "img1", "image": {"url": "https://example.com/watch.jpg"}}
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://example.com/watch.jpg"

    def test_title_truncation(self):
        from app.agents.adapters.chrono24_caller import _normalize_listing

        item = {"id": "long", "title": "W" * 600}
        hit = _normalize_listing(item)
        assert len(hit["title"]) <= 500


# ---------------------------------------------------------------------------
# Cross-reference price tests
# ---------------------------------------------------------------------------

class TestCrossReferencePrice:
    """Tests for Chrono24Caller._cross_reference_price()."""

    def test_no_existing_hits(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        hits = [{"source": "chrono24", "price": 5000}]
        result = caller._cross_reference_price(hits, existing_hits=None)
        assert "_reliability_override" not in result[0]

    def test_no_deviation(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        hits = [{"source": "chrono24", "price": 5000}]
        existing = [
            {"source": "ebay", "price": 5200},
            {"source": "bezel", "price": 4800},
        ]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        # Deviation is small, no override
        assert "_reliability_override" not in result[0]

    def test_high_deviation_degrades_reliability(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller, CHRONO24_DEGRADED_RELIABILITY

        caller = Chrono24Caller(enabled=True)
        # Chrono24 price 10000 vs median 5000 = 100% deviation
        hits = [{"source": "chrono24", "price": 10000}]
        existing = [
            {"source": "ebay", "price": 5000},
            {"source": "bezel", "price": 5000},
        ]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        assert result[0]["_reliability_override"] == CHRONO24_DEGRADED_RELIABILITY

    def test_exactly_at_threshold(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller, PRICE_DEVIATION_THRESHOLD

        caller = Chrono24Caller(enabled=True)
        # 40% deviation exactly — should NOT trigger (> not >=)
        median = 5000
        # price that is exactly 40% above median = 7000
        hits = [{"source": "chrono24", "price": 7000}]
        existing = [
            {"source": "ebay", "price": 5000},
        ]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        # 7000 vs 5000 = 40% which is not > 40%, so no override
        assert "_reliability_override" not in result[0]

    def test_just_above_threshold(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller, CHRONO24_DEGRADED_RELIABILITY

        caller = Chrono24Caller(enabled=True)
        # Just above 40% deviation
        hits = [{"source": "chrono24", "price": 7100}]
        existing = [
            {"source": "ebay", "price": 5000},
        ]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        assert result[0]["_reliability_override"] == CHRONO24_DEGRADED_RELIABILITY

    def test_skip_zero_price_hits(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        hits = [{"source": "chrono24", "price": 0}]
        existing = [{"source": "ebay", "price": 5000}]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        assert "_reliability_override" not in result[0]

    def test_skip_chrono24_in_existing(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        # Only chrono24 in existing — should have no reference prices
        hits = [{"source": "chrono24", "price": 10000}]
        existing = [{"source": "chrono24", "price": 5000}]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        assert "_reliability_override" not in result[0]

    def test_multiple_hits_mixed(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller, CHRONO24_DEGRADED_RELIABILITY

        caller = Chrono24Caller(enabled=True)
        hits = [
            {"source": "chrono24", "price": 5000},   # normal
            {"source": "chrono24", "price": 15000},  # inflated (200% deviation)
        ]
        existing = [
            {"source": "ebay", "price": 5000},
            {"source": "bezel", "price": 5200},
        ]
        result = caller._cross_reference_price(hits, existing_hits=existing)
        assert "_reliability_override" not in result[0]
        assert result[1]["_reliability_override"] == CHRONO24_DEGRADED_RELIABILITY


# ---------------------------------------------------------------------------
# Page parsing tests
# ---------------------------------------------------------------------------

class TestParseSearchPage:
    """Tests for Chrono24Caller._parse_search_page()."""

    def test_extracts_ids_from_urls(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        html = '''
        <a href="/rolex/submariner/id12345.htm">Rolex Submariner</a>
        <a href="/omega/speedmaster/id67890.htm">Omega Speedmaster</a>
        '''
        results = caller._parse_search_page(html, "watch", 10)
        assert len(results) == 2
        assert results[0]["raw_id"] == "chrono24-12345"
        assert results[1]["raw_id"] == "chrono24-67890"

    def test_extracts_ids_from_data_attributes(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        html = '<div data-article-id="11111"></div><div data-article-id="22222"></div>'
        results = caller._parse_search_page(html, "watch", 10)
        assert len(results) == 2
        assert results[0]["raw_id"] == "chrono24-11111"

    def test_extracts_prices_from_data_attribute(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        html = '''
        <a href="/id11111.htm">Watch 1</a> data-price="5000"
        <a href="/id22222.htm">Watch 2</a> data-price="8500.50"
        '''
        results = caller._parse_search_page(html, "watch", 10)
        assert len(results) >= 2
        assert results[0]["price"] == 5000.0
        assert results[1]["price"] == 8500.50

    def test_respects_limit(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        html = "".join(f'<a href="/id{i}.htm">Watch</a>' for i in range(50))
        results = caller._parse_search_page(html, "watch", 5)
        assert len(results) <= 5

    def test_marks_sold(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        html = '<a href="/id99999.htm">Watch</a>'
        results = caller._parse_search_page(html, "watch", 10, is_sold=True)
        assert results[0]["is_sold"] is True

    def test_empty_html(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=True)
        results = caller._parse_search_page("", "watch", 10)
        assert results == []


# ---------------------------------------------------------------------------
# Chrono24Caller class tests
# ---------------------------------------------------------------------------

class TestChrono24Caller:
    """Tests for the Chrono24Caller class."""

    def test_configured(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        assert Chrono24Caller(enabled=True).configured is True
        assert Chrono24Caller(enabled=False).configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=False)
        results = await caller.search("Rolex")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_not_configured(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=False)
        results = await caller.sold_comps("Omega")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_html_response(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        chrono24_circuit.reset()

        html = '''
        <a href="/rolex/submariner/id12345.htm" class="article-title">Rolex Submariner</a>
        data-price="15000"
        <a href="/omega/speedmaster/id67890.htm" class="article-title">Omega Speedmaster</a>
        data-price="7500"
        '''

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Rolex", limit=10)
        assert len(results) == 2
        assert results[0]["source"] == "chrono24"
        assert results[0]["price"] == 15000.0

    @pytest.mark.asyncio
    async def test_search_with_cross_reference(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller, CHRONO24_DEGRADED_RELIABILITY

        chrono24_circuit.reset()

        html = '<a href="/id99999.htm">Watch</a> data-price="20000"'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        existing_hits = [
            {"source": "ebay", "price": 5000},
            {"source": "bezel", "price": 5200},
        ]
        results = await caller.search("Inflated Watch", existing_hits=existing_hits)
        assert len(results) == 1
        assert results[0]["_reliability_override"] == CHRONO24_DEGRADED_RELIABILITY

    @pytest.mark.asyncio
    async def test_search_handles_non_200(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        chrono24_circuit.reset()

        mock_response = MagicMock(status_code=503)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Rolex")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        chrono24_circuit.reset()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("DNS resolution failed"))
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Rolex")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_with_html(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        chrono24_circuit.reset()

        html = '<a href="/id55555.htm">Sold Watch</a> data-price="8000"'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        results = await caller.sold_comps("Omega")
        assert len(results) == 1
        assert results[0]["is_sold"] is True
        assert results[0]["price"] == 8000.0

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        caller = Chrono24Caller(enabled=False)
        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        mock_client = AsyncMock()
        mock_client.is_closed = False

        caller = Chrono24Caller(enabled=True)
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self):
        from app.agents.adapters.chrono24_caller import Chrono24Caller

        for _ in range(10):
            chrono24_circuit.record_failure()

        caller = Chrono24Caller(enabled=True)
        results = await caller.search("anything")
        assert results == []

        chrono24_circuit.reset()


# ---------------------------------------------------------------------------
# Constants / module-level tests
# ---------------------------------------------------------------------------

class TestChrono24Constants:
    """Tests for module-level constants."""

    def test_supported_categories(self):
        from app.agents.adapters.chrono24_caller import SUPPORTED_CATEGORIES

        assert "watches" in SUPPORTED_CATEGORIES

    def test_reliability_scores(self):
        from app.agents.adapters.chrono24_caller import (
            CHRONO24_SOURCE_RELIABILITY,
            CHRONO24_SOLD_RELIABILITY,
            CHRONO24_DEGRADED_RELIABILITY,
        )

        assert CHRONO24_SOURCE_RELIABILITY == 0.70
        assert CHRONO24_SOLD_RELIABILITY == 0.75
        assert CHRONO24_DEGRADED_RELIABILITY == 0.55

    def test_deviation_threshold(self):
        from app.agents.adapters.chrono24_caller import PRICE_DEVIATION_THRESHOLD

        assert PRICE_DEVIATION_THRESHOLD == 0.40
