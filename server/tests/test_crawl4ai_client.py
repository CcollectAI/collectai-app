"""
Tests for app/lib/crawl4ai_client.py — Crawl4AI wrapper.
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Ensure Crawl4AI is disabled by default in tests
os.environ["CRAWL4AI_ENABLED"] = "false"

# Mock the crawl4ai package so imports don't fail when it's not installed
_mock_crawl4ai = types.ModuleType("crawl4ai")
_mock_crawl4ai.AsyncWebCrawler = MagicMock
_mock_crawl4ai.BrowserConfig = MagicMock
_mock_crawl4ai.CrawlerRunConfig = MagicMock
sys.modules.setdefault("crawl4ai", _mock_crawl4ai)


class TestConfigured:
    """Tests for configured()."""

    def test_not_configured_by_default(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.lib.crawl4ai_client import configured

        assert configured() is False

    def test_configured_when_enabled(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import configured

        assert configured() is True


class TestScrapeUrl:
    """Tests for scrape_url()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.lib.crawl4ai_client import scrape_url

        result = await scrape_url("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_success(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import scrape_url

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.markdown = "# Hello World\nPrice: $29.99"
        mock_result.url = "https://example.com"
        mock_result.title = "Hello World"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)
        monkeypatch.setattr("app.lib.crawl4ai_client._semaphore", asyncio.Semaphore(3))

        result = await scrape_url("https://example.com")
        assert result is not None
        assert result["markdown"] == "# Hello World\nPrice: $29.99"
        assert result["metadata"]["title"] == "Hello World"
        assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_scrape_failure_returns_none(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import scrape_url

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "Timeout"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)
        monkeypatch.setattr("app.lib.crawl4ai_client._semaphore", asyncio.Semaphore(3))

        result = await scrape_url("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_exception_returns_none(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import scrape_url

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=RuntimeError("browser crash"))

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)
        monkeypatch.setattr("app.lib.crawl4ai_client._semaphore", asyncio.Semaphore(3))

        result = await scrape_url("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_with_css_selector(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import scrape_url

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.markdown = "Filtered content"
        mock_result.url = "https://example.com"
        mock_result.title = "Page"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)
        monkeypatch.setattr("app.lib.crawl4ai_client._semaphore", asyncio.Semaphore(3))

        result = await scrape_url("https://example.com", css_selector=".listings")
        assert result is not None
        assert result["markdown"] == "Filtered content"

    @pytest.mark.asyncio
    async def test_scrape_with_wait_for(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import scrape_url

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.markdown = "JS content loaded"
        mock_result.url = "https://stockx.com/search"
        mock_result.title = "StockX"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)
        monkeypatch.setattr("app.lib.crawl4ai_client._semaphore", asyncio.Semaphore(3))

        result = await scrape_url("https://stockx.com/search", wait_for="[data-testid='product-tile']")
        assert result is not None
        assert result["markdown"] == "JS content loaded"


class TestCrawlUrls:
    """Tests for crawl_urls()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.lib.crawl4ai_client import crawl_urls

        results = await crawl_urls(["https://a.com", "https://b.com"])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_crawl_success(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True)
        from app.lib.crawl4ai_client import crawl_urls

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.markdown = "Content"
        mock_result.url = "https://a.com"
        mock_result.title = "Page"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)
        monkeypatch.setattr("app.lib.crawl4ai_client._semaphore", asyncio.Semaphore(3))

        results = await crawl_urls(["https://a.com", "https://b.com"])
        assert len(results) == 2


class TestClose:
    """Tests for close()."""

    @pytest.mark.asyncio
    async def test_close_resets_crawler(self, monkeypatch):
        from app.lib.crawl4ai_client import close

        mock_crawler = AsyncMock()
        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", mock_crawler)

        await close()
        mock_crawler.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_crawler(self, monkeypatch):
        from app.lib.crawl4ai_client import close

        monkeypatch.setattr("app.lib.crawl4ai_client._crawler", None)
        await close()  # should not raise


class TestCrawlSite:
    """Tests for crawl_site()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False)
        from app.lib.crawl4ai_client import crawl_site

        results = await crawl_site("https://example.com")
        assert results == []
