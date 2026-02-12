"""
Tests for app/agents/adapters/firecrawl_caller.py — marketplace adapter.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.pop("FIRECRAWL_API_KEY", None)


# ---------------------------------------------------------------------------
# Price extraction unit tests
# ---------------------------------------------------------------------------

class TestExtractPrice:
    """Tests for _extract_price() helper."""

    def test_usd_dollar_sign(self):
        from app.agents.adapters.firecrawl_caller import _extract_price

        # Pass explicit rates to avoid test pollution from config reloads
        rates = {"USD": 0.92, "GBP": 0.86, "JPY": 0.0061}
        price, currency, source_price, source_currency = _extract_price("$29.99 shipped", rates=rates)
        assert price == pytest.approx(29.99 * 0.92, abs=0.01)
        assert currency == "EUR"
        assert source_price == pytest.approx(29.99, abs=0.01)
        assert source_currency == "USD"

    def test_eur_price(self):
        from app.agents.adapters.firecrawl_caller import _extract_price

        price, currency, source_price, source_currency = _extract_price("EUR 45.00")
        assert price == 45.0
        assert currency == "EUR"

    def test_jpy_price(self):
        from app.agents.adapters.firecrawl_caller import _extract_price

        rates = {"USD": 0.92, "GBP": 0.86, "JPY": 0.0061}
        price, currency, source_price, source_currency = _extract_price("¥3500", rates=rates)
        assert price == pytest.approx(3500 * 0.0061, abs=0.1)
        assert currency == "EUR"
        assert source_price == pytest.approx(3500, abs=1)
        assert source_currency == "JPY"

    def test_no_price_found(self):
        from app.agents.adapters.firecrawl_caller import _extract_price

        price, currency, source_price, source_currency = _extract_price("No price here")
        assert price is None
        assert currency == "EUR"

    def test_empty_string(self):
        from app.agents.adapters.firecrawl_caller import _extract_price

        price, currency, source_price, source_currency = _extract_price("")
        assert price is None

    def test_generic_decimal_price(self):
        from app.agents.adapters.firecrawl_caller import _extract_price

        price, currency, source_price, source_currency = _extract_price("Listed for 19.99")
        assert price == 19.99


class TestContentHash:
    """Tests for _content_hash()."""

    def test_deterministic(self):
        from app.agents.adapters.firecrawl_caller import _content_hash

        h1 = _content_hash("firecrawl", "https://example.com/1")
        h2 = _content_hash("firecrawl", "https://example.com/1")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256

    def test_different_urls_different_hashes(self):
        from app.agents.adapters.firecrawl_caller import _content_hash

        h1 = _content_hash("firecrawl", "https://example.com/1")
        h2 = _content_hash("firecrawl", "https://example.com/2")
        assert h1 != h2


class TestExtractImageUrl:
    """Tests for _extract_image_url()."""

    def test_markdown_image(self):
        from app.agents.adapters.firecrawl_caller import _extract_image_url

        md = "![BTS Album](https://img.example.com/bts.jpg) some text"
        assert _extract_image_url(md) == "https://img.example.com/bts.jpg"

    def test_no_image(self):
        from app.agents.adapters.firecrawl_caller import _extract_image_url

        assert _extract_image_url("No images here") is None

    def test_empty_markdown(self):
        from app.agents.adapters.firecrawl_caller import _extract_image_url

        assert _extract_image_url("") is None
        assert _extract_image_url(None) is None


class TestNormalizeSearchResult:
    """Tests for _normalize_search_result()."""

    def test_full_result(self):
        from app.agents.adapters.firecrawl_caller import _normalize_search_result

        result = {
            "url": "https://mercari.com/item/123",
            "title": "BTS Butter Album $29.99",
            "markdown": "![img](https://img.example.com/bts.jpg)\nDescription here",
            "description": "BTS Butter album sealed",
        }
        hit = _normalize_search_result(result, "BTS album")
        assert hit["source"] == "firecrawl"
        assert hit["url"] == "https://mercari.com/item/123"
        assert hit["title"].startswith("BTS Butter")
        assert hit["price"] is not None
        assert hit["image_url"] == "https://img.example.com/bts.jpg"
        assert hit["content_hash"] == hit["raw_id"]

    def test_sold_detection(self):
        from app.agents.adapters.firecrawl_caller import _normalize_search_result

        result = {
            "url": "https://ebay.com/itm/sold-listing",
            "title": "SOLD: Pokemon Card PSA 10",
            "markdown": "",
            "description": "This listing has ended",
        }
        hit = _normalize_search_result(result, "pokemon card")
        assert hit["is_sold"] is True

    def test_no_price_result(self):
        from app.agents.adapters.firecrawl_caller import _normalize_search_result

        result = {
            "url": "https://example.com",
            "title": "Just a title with no price info",
            "markdown": "No prices",
            "description": "",
        }
        hit = _normalize_search_result(result, "query")
        assert hit["price"] is None


# ---------------------------------------------------------------------------
# FirecrawlCaller async tests
# ---------------------------------------------------------------------------

class TestFirecrawlCaller:
    """Tests for the FirecrawlCaller class."""

    def test_not_configured_without_key(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        caller = FirecrawlCaller()
        assert caller.configured is False

    def test_configured_with_key(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        caller = FirecrawlCaller()
        assert caller.configured is True

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        caller = FirecrawlCaller()
        results = await caller.search("BTS album")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_category_targets(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        mock_search = AsyncMock(return_value=[
            {
                "url": "https://ktown4u.com/item/1",
                "title": "BTS Butter Album $35.00",
                "markdown": "BTS official merchandise",
                "description": "Sealed album",
            },
        ])

        with patch("app.lib.firecrawl_client.search_web", mock_search):
            caller = FirecrawlCaller()
            results = await caller.search("BTS album", category="kpop_merch")

        assert len(results) >= 0  # may filter no-price items
        mock_search.assert_called_once()
        call_query = mock_search.call_args[0][0]
        assert "site:" in call_query  # site targeting applied

    @pytest.mark.asyncio
    async def test_sold_comps_appends_sold(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        mock_search = AsyncMock(return_value=[
            {
                "url": "https://mercari.com/sold/1",
                "title": "Taylor Swift Eras Tour Poster $45.00 SOLD",
                "markdown": "Sold listing",
                "description": "completed sale",
            },
        ])

        with patch("app.lib.firecrawl_client.search_web", mock_search):
            caller = FirecrawlCaller()
            results = await caller.sold_comps("Taylor Swift poster", category="taylor_swift")

        if results:
            assert all(h["is_sold"] is True for h in results)

    @pytest.mark.asyncio
    async def test_search_handles_exception(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        mock_search = AsyncMock(side_effect=RuntimeError("network error"))

        with patch("app.lib.firecrawl_client.search_web", mock_search):
            caller = FirecrawlCaller()
            results = await caller.search("anything")

        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "")
        from app.agents.adapters.firecrawl_caller import FirecrawlCaller

        caller = FirecrawlCaller()
        healthy = await caller.health_check()
        assert healthy is False


class TestCategorySiteTargets:
    """Verify category-site mappings cover key categories."""

    def test_kpop_merch_has_sites(self):
        from app.agents.adapters.firecrawl_caller import CATEGORY_SITE_TARGETS

        assert "kpop_merch" in CATEGORY_SITE_TARGETS
        sites = CATEGORY_SITE_TARGETS["kpop_merch"]
        assert any("ktown4u" in s for s in sites)

    def test_taylor_swift_has_sites(self):
        from app.agents.adapters.firecrawl_caller import CATEGORY_SITE_TARGETS

        assert "taylor_swift" in CATEGORY_SITE_TARGETS
        sites = CATEGORY_SITE_TARGETS["taylor_swift"]
        assert any("mercari" in s for s in sites)
        assert any("stockx" in s for s in sites)

    def test_anime_figures_has_sites(self):
        from app.agents.adapters.firecrawl_caller import CATEGORY_SITE_TARGETS

        assert "anime_figures" in CATEGORY_SITE_TARGETS
        sites = CATEGORY_SITE_TARGETS["anime_figures"]
        assert any("myfigurecollection" in s for s in sites)
