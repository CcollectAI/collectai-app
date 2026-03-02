"""
Tests for app/agents/adapters/keh_caller.py -- KEH Camera marketplace adapter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers.circuit_breaker import keh_circuit


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeListing:
    """Tests for _normalize_listing()."""

    def test_basic_normalization(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {
            "sku": "KEH-12345",
            "name": "Leica M6 TTL 0.72 Black",
            "price": 2899.99,
            "image_url": "https://www.keh.com/media/leica-m6.jpg",
            "grade": "EX+",
            "url_key": "leica-m6-ttl-072-black.html",
        }
        hit = _normalize_listing(item)
        assert hit["source"] == "keh"
        assert hit["raw_id"] == "keh-KEH-12345"
        assert "Leica M6" in hit["title"]
        assert hit["price"] == 2899.99
        assert hit["currency"] == "USD"
        assert hit["condition"] == "Excellent Plus"
        assert hit["image_url"] == "https://www.keh.com/media/leica-m6.jpg"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "keh.com/shop/" in hit["url"]

    def test_like_new_grade(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "LN1", "name": "Canon AE-1", "price": 450, "grade": "LN"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Like New"

    def test_bargain_grade(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "BGN1", "name": "Nikon F3", "price": 200, "grade": "BGN"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Bargain"

    def test_ugly_grade(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "UG1", "name": "Pentax K1000", "price": 50, "grade": "UG"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Ugly"

    def test_excellent_grade(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "EX1", "name": "Olympus OM-1", "price": 350, "grade": "EX"}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Excellent"

    def test_no_grade(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "NG1", "name": "Minolta SRT 101"}
        hit = _normalize_listing(item)
        assert hit["condition"] is None

    def test_empty_item(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        hit = _normalize_listing({})
        assert hit["source"] == "keh"
        assert hit["raw_id"] == "keh-"
        assert hit["price"] == 0.0
        assert hit["title"] == "Unknown Camera"

    def test_nested_price_object(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {
            "sku": "NP1",
            "name": "Hasselblad 500C",
            "price": {"amount": 1200, "currency": "USD"},
        }
        hit = _normalize_listing(item)
        assert hit["price"] == 1200.0

    def test_title_truncation(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "long", "name": "A" * 600}
        hit = _normalize_listing(item)
        assert len(hit["title"]) <= 500

    def test_fallback_id_fields(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"id": "fallback-id", "name": "Test Camera"}
        hit = _normalize_listing(item)
        assert hit["raw_id"] == "keh-fallback-id"

    def test_entity_id_fallback(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"entity_id": "eid-999", "name": "Test Camera 2"}
        hit = _normalize_listing(item)
        assert hit["raw_id"] == "keh-eid-999"

    def test_url_full_url_passthrough(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "x", "url": "https://www.keh.com/shop/custom-url"}
        hit = _normalize_listing(item)
        assert hit["url"] == "https://www.keh.com/shop/custom-url"

    def test_condition_dict(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "cd1", "condition": {"label": "EX+", "code": "EX+"}}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Excellent Plus"

    def test_images_list(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {
            "sku": "img1",
            "images": [{"url": "https://www.keh.com/photo.jpg"}],
        }
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://www.keh.com/photo.jpg"

    def test_thumbnail_fallback(self):
        from app.agents.adapters.keh_caller import _normalize_listing

        item = {"sku": "th1", "thumbnail": "https://www.keh.com/thumb.jpg"}
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://www.keh.com/thumb.jpg"


# ---------------------------------------------------------------------------
# Grade normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeGrade:
    """Tests for _normalize_grade()."""

    def test_all_short_codes(self):
        from app.agents.adapters.keh_caller import _normalize_grade

        assert _normalize_grade("LN") == "Like New"
        assert _normalize_grade("EX+") == "Excellent Plus"
        assert _normalize_grade("EX") == "Excellent"
        assert _normalize_grade("BGN") == "Bargain"
        assert _normalize_grade("UG") == "Ugly"

    def test_full_names(self):
        from app.agents.adapters.keh_caller import _normalize_grade

        assert _normalize_grade("Like New") == "Like New"
        assert _normalize_grade("Excellent") == "Excellent"
        assert _normalize_grade("Bargain") == "Bargain"

    def test_none_input(self):
        from app.agents.adapters.keh_caller import _normalize_grade

        assert _normalize_grade(None) is None

    def test_empty_string(self):
        from app.agents.adapters.keh_caller import _normalize_grade

        assert _normalize_grade("") is None

    def test_unknown_grade(self):
        from app.agents.adapters.keh_caller import _normalize_grade

        assert _normalize_grade("Custom Grade") == "Custom Grade"

    def test_whitespace_stripped(self):
        from app.agents.adapters.keh_caller import _normalize_grade

        assert _normalize_grade("  EX+  ") == "Excellent Plus"


# ---------------------------------------------------------------------------
# KEHCaller class tests
# ---------------------------------------------------------------------------

class TestKEHCaller:
    """Tests for the KEHCaller class."""

    def test_configured_default(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=False)
        results = await caller.search("Leica M6")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_always_returns_empty(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=True)
        results = await caller.sold_comps("Leica M6")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_api_success(self):
        from app.agents.adapters.keh_caller import KEHCaller

        keh_circuit.reset()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "products": [
                {
                    "sku": "KEH-001",
                    "name": "Leica M6 TTL Black",
                    "price": 2899.99,
                    "grade": "EX+",
                    "image_url": "https://www.keh.com/media/leica.jpg",
                    "url_key": "leica-m6-ttl-black.html",
                },
                {
                    "sku": "KEH-002",
                    "name": "Nikon FM2 Silver",
                    "price": 449.00,
                    "grade": "EX",
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Leica", limit=5)
        assert len(results) == 2
        assert results[0]["source"] == "keh"
        assert results[0]["raw_id"] == "keh-KEH-001"
        assert results[0]["price"] == 2899.99
        assert results[0]["condition"] == "Excellent Plus"
        assert results[1]["price"] == 449.00
        assert results[1]["condition"] == "Excellent"

    @pytest.mark.asyncio
    async def test_search_falls_back_to_scrape(self):
        from app.agents.adapters.keh_caller import KEHCaller

        keh_circuit.reset()

        # First call returns 403 (API blocked), second returns HTML
        html_content = (
            '<a href="/shop/leica-m6.html" class="product-name">Leica M6</a> '
            '$2,899.99 EX+ '
            '<a href="/shop/nikon-fm2.html" class="product-name">Nikon FM2</a> '
            '$449.00 BGN'
        )
        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"products": []})),
            MagicMock(status_code=200, text=html_content),
        ]
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Leica")
        assert len(results) == 2
        assert results[0]["raw_id"] == "keh-leica-m6.html"
        assert results[0]["price"] == 2899.99

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.keh_caller import KEHCaller

        keh_circuit.reset()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Leica")
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=False)
        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.keh_caller import KEHCaller

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_health_check_rate_limited(self):
        from app.agents.adapters.keh_caller import KEHCaller

        mock_response = MagicMock(status_code=403)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True  # 403 means reachable

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        from app.agents.adapters.keh_caller import KEHCaller

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("DNS failure"))
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.keh_caller import KEHCaller

        mock_client = AsyncMock()
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=True)
        caller._http = None
        await caller.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self):
        from app.agents.adapters.keh_caller import KEHCaller

        # Trip the circuit breaker
        for _ in range(10):
            keh_circuit.record_failure()

        caller = KEHCaller(enabled=True)
        results = await caller.search("anything")
        assert results == []

        # Reset for other tests
        keh_circuit.reset()

    @pytest.mark.asyncio
    async def test_search_api_non_200_triggers_scrape(self):
        from app.agents.adapters.keh_caller import KEHCaller

        keh_circuit.reset()

        html_content = (
            '<a href="/shop/canon-ae1.html" class="product-name">Canon AE-1</a> $299.00 EX'
        )
        responses = [
            MagicMock(status_code=500),
            MagicMock(status_code=200, text=html_content),
        ]
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Canon AE-1")
        assert len(results) == 1
        assert results[0]["price"] == 299.00

    @pytest.mark.asyncio
    async def test_scrape_non_200(self):
        from app.agents.adapters.keh_caller import KEHCaller

        keh_circuit.reset()

        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"products": []})),
            MagicMock(status_code=503),
        ]
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.is_closed = False

        caller = KEHCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Test")
        assert results == []


# ---------------------------------------------------------------------------
# Parse search page tests
# ---------------------------------------------------------------------------

class TestParseSearchPage:
    """Tests for _parse_search_page HTML parsing."""

    def test_parse_empty_html(self):
        from app.agents.adapters.keh_caller import KEHCaller

        caller = KEHCaller(enabled=True)
        results = caller._parse_search_page("<html><body></body></html>", 10)
        assert results == []

    def test_parse_with_products(self):
        from app.agents.adapters.keh_caller import KEHCaller

        html = '''
        <div class="product-name"><a href="/shop/leica-m6.html">Leica M6 TTL</a></div>
        <span>$2,899.99</span>
        <span>EX+</span>
        <img src="https://www.keh.com/media/leica.jpg" />
        '''
        caller = KEHCaller(enabled=True)
        results = caller._parse_search_page(html, 10)
        assert len(results) == 1
        assert results[0]["raw_id"] == "keh-leica-m6.html"
        assert results[0]["price"] == 2899.99

    def test_parse_respects_limit(self):
        from app.agents.adapters.keh_caller import KEHCaller

        html = '''
        <a href="/shop/cam1.html">Cam1</a> $100
        <a href="/shop/cam2.html">Cam2</a> $200
        <a href="/shop/cam3.html">Cam3</a> $300
        '''
        caller = KEHCaller(enabled=True)
        results = caller._parse_search_page(html, 2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Constants / module-level tests
# ---------------------------------------------------------------------------

class TestKEHConstants:
    """Tests for module-level constants."""

    def test_supported_categories(self):
        from app.agents.adapters.keh_caller import SUPPORTED_CATEGORIES

        assert "vintage_cameras" in SUPPORTED_CATEGORIES

    def test_reliability_score(self):
        from app.agents.adapters.keh_caller import KEH_SOURCE_RELIABILITY

        assert KEH_SOURCE_RELIABILITY == 0.85

    def test_grade_map_completeness(self):
        from app.agents.adapters.keh_caller import KEH_GRADE_MAP

        assert "LN" in KEH_GRADE_MAP
        assert "EX+" in KEH_GRADE_MAP
        assert "EX" in KEH_GRADE_MAP
        assert "BGN" in KEH_GRADE_MAP
        assert "UG" in KEH_GRADE_MAP


# ---------------------------------------------------------------------------
# Region config integration tests
# ---------------------------------------------------------------------------

class TestKEHRegionConfig:
    """Tests that KEH is properly configured in region marketplace config."""

    def test_americas_enabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("americas", "keh") is True

    def test_europe_enabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("europe", "keh") is True

    def test_japan_disabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("japan", "keh") is False

    def test_other_enabled(self):
        from app.lib.region_marketplace_config import should_use_adapter

        assert should_use_adapter("other", "keh") is True


# ---------------------------------------------------------------------------
# Circuit breaker integration tests
# ---------------------------------------------------------------------------

class TestKEHCircuitBreaker:
    """Tests for KEH circuit breaker integration."""

    def test_circuit_exists(self):
        from workers.circuit_breaker import keh_circuit

        assert keh_circuit.name == "keh"
        assert keh_circuit.max_failures == 5

    def test_circuit_in_all_status(self):
        from workers.circuit_breaker import all_circuit_status

        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "keh" in names
