"""
Tests for app/agents/adapters/mpb_caller.py -- MPB camera marketplace adapter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers.circuit_breaker import mpb_circuit


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeListing:
    """Tests for _normalize_listing()."""

    def test_basic_normalization_us(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {
            "id": "mpb-12345",
            "name": "Leica M6 TTL 0.72 Black",
            "price": 2499.00,
            "image_url": "https://www.mpb.com/media/leica-m6.jpg",
            "condition": "Excellent",
            "slug": "leica-m6-ttl-072-black",
        }
        hit = _normalize_listing(item, region="americas")
        assert hit["source"] == "mpb"
        assert hit["raw_id"] == "mpb-mpb-12345"
        assert "Leica M6" in hit["title"]
        assert hit["price"] == 2499.00
        assert hit["currency"] == "USD"
        assert hit["condition"] == "Excellent"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "mpb.com/en-us/product/" in hit["url"]

    def test_uk_region_gbp(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {
            "id": "uk-001",
            "name": "Canon AE-1 Program",
            "price": 199.00,
            "condition": "Good",
        }
        hit = _normalize_listing(item, region="europe")
        assert hit["currency"] == "GBP"
        assert hit["source_currency"] == "GBP"
        assert "mpb.com/en-uk/product/" in hit["url"]

    def test_default_region_usd(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "def1", "name": "Camera", "price": 100}
        hit = _normalize_listing(item, region=None)
        assert hit["currency"] == "USD"
        assert "mpb.com/en-us/product/" in hit["url"]

    def test_like_new_condition(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "ln1", "name": "Test", "condition": "Like New"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Like New"

    def test_well_used_condition(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "wu1", "name": "Test", "condition": "Well Used"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Well Used"

    def test_heavily_used_condition(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "hu1", "name": "Test", "condition": "Heavily Used"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Heavily Used"

    def test_no_condition(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "nc1", "name": "Test"}
        hit = _normalize_listing(item)
        assert hit["condition"] is None

    def test_empty_item(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        hit = _normalize_listing({})
        assert hit["source"] == "mpb"
        assert hit["raw_id"] == "mpb-"
        assert hit["price"] == 0.0
        assert hit["title"] == "Unknown Camera"

    def test_nested_price_object(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {
            "id": "np1",
            "name": "Hasselblad 500C",
            "price": {"amount": 1200, "currency": "USD"},
        }
        hit = _normalize_listing(item)
        assert hit["price"] == 1200.0

    def test_title_truncation(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "long", "name": "A" * 600}
        hit = _normalize_listing(item)
        assert len(hit["title"]) <= 500

    def test_url_passthrough(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "x", "url": "https://www.mpb.com/en-us/product/custom"}
        hit = _normalize_listing(item)
        assert hit["url"] == "https://www.mpb.com/en-us/product/custom"

    def test_condition_dict(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "cd1", "condition": {"label": "Excellent", "name": "EX"}}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Excellent"

    def test_images_list(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {
            "id": "img1",
            "images": [{"url": "https://www.mpb.com/photo.jpg"}],
        }
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://www.mpb.com/photo.jpg"

    def test_imageurl_field(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "iu1", "imageUrl": "https://www.mpb.com/img.jpg"}
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://www.mpb.com/img.jpg"

    def test_thumbnail_fallback(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"id": "th1", "thumbnail": "https://www.mpb.com/thumb.jpg"}
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://www.mpb.com/thumb.jpg"

    def test_slug_fallback(self):
        from app.agents.adapters.mpb_caller import _normalize_listing

        item = {"slug": "nikon-f3-body"}
        hit = _normalize_listing(item)
        assert hit["raw_id"] == "mpb-nikon-f3-body"
        assert "nikon-f3-body" in hit["url"]


# ---------------------------------------------------------------------------
# Grade normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeGrade:
    """Tests for _normalize_grade()."""

    def test_all_grades(self):
        from app.agents.adapters.mpb_caller import _normalize_grade

        assert _normalize_grade("Like New") == "Like New"
        assert _normalize_grade("Excellent") == "Excellent"
        assert _normalize_grade("Good") == "Good"
        assert _normalize_grade("Well Used") == "Well Used"
        assert _normalize_grade("Heavily Used") == "Heavily Used"

    def test_case_insensitive(self):
        from app.agents.adapters.mpb_caller import _normalize_grade

        assert _normalize_grade("like new") == "Like New"
        assert _normalize_grade("excellent") == "Excellent"
        assert _normalize_grade("good") == "Good"

    def test_none_input(self):
        from app.agents.adapters.mpb_caller import _normalize_grade

        assert _normalize_grade(None) is None

    def test_empty_string(self):
        from app.agents.adapters.mpb_caller import _normalize_grade

        assert _normalize_grade("") is None

    def test_unknown_grade(self):
        from app.agents.adapters.mpb_caller import _normalize_grade

        assert _normalize_grade("Custom") == "Custom"

    def test_whitespace_stripped(self):
        from app.agents.adapters.mpb_caller import _normalize_grade

        assert _normalize_grade("  Excellent  ") == "Excellent"


# ---------------------------------------------------------------------------
# MPBCaller class tests
# ---------------------------------------------------------------------------

class TestMPBCaller:
    """Tests for the MPBCaller class."""

    def test_configured_default(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=False)
        results = await caller.search("Leica M6")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_always_returns_empty(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=True)
        results = await caller.sold_comps("Leica M6")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_html_success(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mpb_circuit.reset()

        html_content = '''
        <div class="product-card__title"><a href="/en-us/product/leica-m6-ttl">Leica M6 TTL</a></div>
        <span>$2,499.00</span>
        <span>Excellent</span>
        <img src="https://www.mpb.com/media/leica.jpg" />
        <div class="product-card__title"><a href="/en-us/product/nikon-fm2">Nikon FM2</a></div>
        <span>$399.00</span>
        <span>Good</span>
        '''

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Leica", limit=5)
        assert len(results) == 2
        assert results[0]["source"] == "mpb"
        assert results[0]["raw_id"] == "mpb-leica-m6-ttl"
        assert results[0]["price"] == 2499.00

    @pytest.mark.asyncio
    async def test_search_uk_region(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mpb_circuit.reset()

        html_content = '''
        <div class="product-card__title"><a href="/en-uk/product/canon-ae1">Canon AE-1</a></div>
        <span>\u00a3199.00</span>
        <span>Good</span>
        '''

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Canon", region="europe")
        assert len(results) == 1
        assert results[0]["currency"] == "GBP"
        assert results[0]["price"] == 199.00

    @pytest.mark.asyncio
    async def test_search_non_200(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mpb_circuit.reset()

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mpb_circuit.reset()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Leica")
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=False)
        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_health_check_rate_limited(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mock_response = MagicMock(status_code=403)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True  # 403 means reachable

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("DNS failure"))
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        mock_client = AsyncMock()
        mock_client.is_closed = False

        caller = MPBCaller(enabled=True)
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=True)
        caller._http = None
        await caller.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        # Trip the circuit breaker
        for _ in range(10):
            mpb_circuit.record_failure()

        caller = MPBCaller(enabled=True)
        results = await caller.search("anything")
        assert results == []

        # Reset for other tests
        mpb_circuit.reset()


# ---------------------------------------------------------------------------
# Parse search page tests
# ---------------------------------------------------------------------------

class TestParseSearchPage:
    """Tests for _parse_search_page HTML parsing."""

    def test_parse_empty_html(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        caller = MPBCaller(enabled=True)
        results = caller._parse_search_page("<html><body></body></html>", 10)
        assert results == []

    def test_parse_with_products_us(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        html = '''
        <div class="product-card__title"><a href="/en-us/product/leica-m6">Leica M6</a></div>
        <span>$2,499.00</span>
        <span>Excellent</span>
        '''
        caller = MPBCaller(enabled=True)
        results = caller._parse_search_page(html, 10, region="americas")
        assert len(results) == 1
        assert results[0]["currency"] == "USD"
        assert results[0]["raw_id"] == "mpb-leica-m6"

    def test_parse_with_products_uk(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        html = '''
        <a href="/en-uk/product/canon-ae1">Canon AE-1</a>
        \u00a3199.00
        Good
        '''
        caller = MPBCaller(enabled=True)
        results = caller._parse_search_page(html, 10, region="europe")
        assert len(results) == 1
        assert results[0]["currency"] == "GBP"

    def test_parse_respects_limit(self):
        from app.agents.adapters.mpb_caller import MPBCaller

        html = '''
        <a href="/en-us/product/cam1">Cam1</a> $100
        <a href="/en-us/product/cam2">Cam2</a> $200
        <a href="/en-us/product/cam3">Cam3</a> $300
        '''
        caller = MPBCaller(enabled=True)
        results = caller._parse_search_page(html, 2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Constants / module-level tests
# ---------------------------------------------------------------------------

class TestMPBConstants:
    """Tests for module-level constants."""

    def test_supported_categories(self):
        from app.agents.adapters.mpb_caller import SUPPORTED_CATEGORIES

        assert "vintage_cameras" in SUPPORTED_CATEGORIES

    def test_reliability_score(self):
        from app.agents.adapters.mpb_caller import MPB_SOURCE_RELIABILITY

        assert MPB_SOURCE_RELIABILITY == 0.80

    def test_grade_map_completeness(self):
        from app.agents.adapters.mpb_caller import MPB_GRADE_MAP

        assert "Like New" in MPB_GRADE_MAP
        assert "Excellent" in MPB_GRADE_MAP
        assert "Good" in MPB_GRADE_MAP
        assert "Well Used" in MPB_GRADE_MAP
        assert "Heavily Used" in MPB_GRADE_MAP


# ---------------------------------------------------------------------------
# Region config integration tests
# ---------------------------------------------------------------------------

class TestMPBRegionConfig:
    """Tests that MPB is properly configured in region marketplace config."""

    def test_americas_enabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("americas", "mpb") is True

    def test_europe_enabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("europe", "mpb") is True

    def test_japan_disabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("japan", "mpb") is False

    def test_other_enabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("other", "mpb") is True


# ---------------------------------------------------------------------------
# Circuit breaker integration tests
# ---------------------------------------------------------------------------

class TestMPBCircuitBreaker:
    """Tests for MPB circuit breaker integration."""

    def test_circuit_exists(self):
        from workers.circuit_breaker import mpb_circuit

        assert mpb_circuit.name == "mpb"
        assert mpb_circuit.max_failures == 5

    def test_circuit_in_all_status(self):
        from workers.circuit_breaker import all_circuit_status

        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "mpb" in names
