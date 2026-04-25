"""
Tests for app/agents/adapters/crawl4ai_caller.py — Crawl4AI marketplace adapter.
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["CRAWL4AI_ENABLED"] = "false"

# Mock the crawl4ai package so imports don't fail when it's not installed
_mock_crawl4ai = types.ModuleType("crawl4ai")
_mock_crawl4ai.AsyncWebCrawler = MagicMock
_mock_crawl4ai.BrowserConfig = MagicMock
_mock_crawl4ai.CrawlerRunConfig = MagicMock
sys.modules.setdefault("crawl4ai", _mock_crawl4ai)


# ---------------------------------------------------------------------------
# URL construction tests
# ---------------------------------------------------------------------------

class TestBuildSearchUrl:
    """Tests for Crawl4AICaller._build_search_url()."""

    def test_ebay_url(self):
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        url = caller._build_search_url("pokemon card", "ebay.com")
        assert "ebay.com/sch/i.html" in url
        assert "pokemon+card" in url or "pokemon%20card" in url.lower()

    def test_ebay_sold_url(self):
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        url = caller._build_search_url("pokemon card", "ebay.com", sold=True)
        assert "LH_Complete=1" in url
        assert "LH_Sold=1" in url

    def test_mercari_url(self):
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        url = caller._build_search_url("BTS album", "mercari.com")
        assert "mercari.com/search" in url

    def test_stockx_url(self):
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        url = caller._build_search_url("Air Jordan", "stockx.com")
        assert "stockx.com/search" in url

    def test_fallback_duckduckgo_search(self):
        # Switched from Google to DuckDuckGo /html/ on 2026-04-25 — Google
        # blocks scrapers without an API key; DDG is scrape-friendly.
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        url = caller._build_search_url("rare item", "unknown-site.com")
        assert "duckduckgo.com/html" in url
        assert "unknown-site.com" in url

    def test_bricklink_url(self):
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        url = caller._build_search_url("LEGO 10279", "bricklink.com")
        assert "bricklink.com" in url


# ---------------------------------------------------------------------------
# Listing splitting tests
# ---------------------------------------------------------------------------

class TestSplitIntoListings:
    """Tests for _split_into_listings()."""

    def test_splits_on_blank_lines(self):
        from app.agents.adapters.crawl4ai_caller import _split_into_listings

        markdown = (
            "First listing with enough text to be valid\n\n\n"
            "Second listing with enough text to be valid\n\n\n"
            "Third listing with enough text to be valid"
        )
        parts = _split_into_listings(markdown)
        assert len(parts) == 3

    def test_splits_on_headers(self):
        from app.agents.adapters.crawl4ai_caller import _split_into_listings

        markdown = (
            "# First Product Title and Description\n"
            "Price: $29.99 and more text to reach minimum\n"
            "## Second Product Title and Description\n"
            "Price: $49.99 and more text to reach minimum"
        )
        parts = _split_into_listings(markdown)
        assert len(parts) >= 2

    def test_filters_tiny_fragments(self):
        from app.agents.adapters.crawl4ai_caller import _split_into_listings

        markdown = "tiny\n\n\ntoo short also\n\n\nThis is a proper listing with enough text content"
        parts = _split_into_listings(markdown)
        assert all(len(p) > 30 for p in parts)

    def test_caps_at_max_listings(self):
        from app.agents.adapters.crawl4ai_caller import _split_into_listings

        markdown = "\n\n\n".join([f"Listing number {i} with enough text to be a valid entry" for i in range(50)])
        parts = _split_into_listings(markdown, max_listings=10)
        assert len(parts) <= 10


class TestExtractTitleFromListing:
    """Tests for _extract_title_from_listing()."""

    def test_extracts_first_valid_line(self):
        from app.agents.adapters.crawl4ai_caller import _extract_title_from_listing

        text = "## Pokemon Base Set Charizard Holo PSA 10\nPrice: $500"
        title = _extract_title_from_listing(text)
        assert title is not None
        assert "Pokemon" in title or "Charizard" in title

    def test_returns_none_for_empty(self):
        from app.agents.adapters.crawl4ai_caller import _extract_title_from_listing

        assert _extract_title_from_listing("") is None
        assert _extract_title_from_listing("tiny") is None


# ---------------------------------------------------------------------------
# Crawl4AICaller async tests
# ---------------------------------------------------------------------------

class TestCrawl4AICaller:
    """Tests for the Crawl4AICaller class."""

    def test_not_configured_by_default(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        assert caller.configured is False

    def test_configured_when_enabled(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        assert caller.configured is True

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        results = await caller.search("pokemon card")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_mocked_scrape(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        mock_scrape = AsyncMock(return_value={
            "markdown": (
                "## Pokemon Charizard Base Set Holo Card\n"
                "Price: $299.99\n"
                "![img](https://img.example.com/charizard.jpg)\n"
                "https://ebay.com/itm/123456\n"
            ),
            "metadata": {"title": "Search Results"},
            "url": "https://www.ebay.com/sch/i.html?_nkw=pokemon+charizard",
        })

        with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
            caller = Crawl4AICaller()
            results = await caller.search("pokemon charizard", category="pokemon", limit=5)

        # Should have called scrape_url at least once
        assert mock_scrape.call_count >= 1
        # Results should be MarketHit dicts with source = crawl4ai
        for hit in results:
            assert hit["source"] == "crawl4ai"
            assert hit["price"] is not None

    @pytest.mark.asyncio
    async def test_sold_comps_marks_is_sold(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        mock_scrape = AsyncMock(return_value={
            "markdown": (
                "## SOLD: Taylor Swift Eras Tour Poster\n"
                "Sold for $45.00\n"
                "https://mercari.com/sold/123\n"
            ),
            "metadata": {"title": "Sold Listings"},
            "url": "https://www.mercari.com/search/?keyword=taylor+swift",
        })

        with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
            caller = Crawl4AICaller()
            results = await caller.sold_comps("Taylor Swift poster", category="taylor_swift")

        for hit in results:
            assert hit["is_sold"] is True

    @pytest.mark.asyncio
    async def test_search_handles_scrape_failure(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        mock_scrape = AsyncMock(return_value=None)

        with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
            caller = Crawl4AICaller()
            results = await caller.search("anything")

        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.agents.adapters.crawl4ai_caller import Crawl4AICaller

        caller = Crawl4AICaller()
        healthy = await caller.health_check()
        assert healthy is False


class TestSiteSearchTemplates:
    """Verify search URL templates cover key sites."""

    def test_has_ebay_templates(self):
        from app.agents.adapters.crawl4ai_caller import SITE_SEARCH_TEMPLATES

        assert "ebay.com" in SITE_SEARCH_TEMPLATES
        assert "ebay.de" in SITE_SEARCH_TEMPLATES

    def test_has_mercari_template(self):
        from app.agents.adapters.crawl4ai_caller import SITE_SEARCH_TEMPLATES

        assert "mercari.com" in SITE_SEARCH_TEMPLATES

    def test_has_bricklink_template(self):
        from app.agents.adapters.crawl4ai_caller import SITE_SEARCH_TEMPLATES

        assert "bricklink.com" in SITE_SEARCH_TEMPLATES

    def test_has_jp_auction_template(self):
        from app.agents.adapters.crawl4ai_caller import SITE_SEARCH_TEMPLATES

        assert "yahoo.co.jp/auctions" in SITE_SEARCH_TEMPLATES

    def test_has_kpop_template(self):
        from app.agents.adapters.crawl4ai_caller import SITE_SEARCH_TEMPLATES

        assert "ktown4u.com" in SITE_SEARCH_TEMPLATES
