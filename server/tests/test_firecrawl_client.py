"""
Tests for app/lib/firecrawl_client.py — Firecrawl API wrapper.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.cache import InMemoryCache, reset_backend

# Ensure no real API calls are made
os.environ.pop("FIRECRAWL_API_KEY", None)


@pytest.fixture(autouse=True)
def _fresh_scrape_cache():
    """Reset scrape cache between tests to prevent cross-test pollution."""
    reset_backend(InMemoryCache())
    yield
    reset_backend(None)


class TestConfigured:
    """Tests for configured() and _headers()."""

    def test_not_configured_when_no_key(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "")
        from app.lib.firecrawl_client import configured

        assert configured() is False

    def test_configured_when_key_set(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test-key")
        from app.lib.firecrawl_client import configured

        assert configured() is True

    def test_headers_include_bearer_token(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test-key")
        from app.lib.firecrawl_client import _headers

        h = _headers()
        assert h["Authorization"] == "Bearer fc-test-key"
        assert h["Content-Type"] == "application/json"


class TestScrapeUrl:
    """Tests for scrape_url()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "")
        from app.lib.firecrawl_client import scrape_url

        result = await scrape_url("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_success(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import scrape_url

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "markdown": "# BTS Album\nPrice: $29.99",
                "metadata": {"title": "BTS Album"},
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        result = await scrape_url("https://ebay.com/itm/123")
        assert result is not None
        assert result["markdown"] == "# BTS Album\nPrice: $29.99"
        assert result["metadata"]["title"] == "BTS Album"

    @pytest.mark.asyncio
    async def test_scrape_with_extract_schema(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import scrape_url

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "markdown": "# Test Item",
                "extract": {"title": "Test Item", "price": 19.99},
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        result = await scrape_url(
            "https://ebay.com/itm/123",
            formats=["markdown", "extract"],
            extract_schema=schema,
        )
        assert result is not None
        assert result["extract"]["title"] == "Test Item"
        assert result["extract"]["price"] == 19.99

        # Verify extract format was included in body
        call_args = mock_client.post.call_args
        body = call_args.kwargs["json"]
        assert "extract" in body["formats"]

    @pytest.mark.asyncio
    async def test_scrape_rate_limited(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import scrape_url

        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        result = await scrape_url("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_http_error(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import scrape_url

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        result = await scrape_url("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scrape_default_format_is_markdown(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import scrape_url

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"markdown": "hello"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        await scrape_url("https://example.com")  # no formats arg

        call_args = mock_client.post.call_args
        body = call_args.kwargs["json"]
        assert body["formats"] == ["markdown"]


class TestSearchWeb:
    """Tests for search_web()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "")
        from app.lib.firecrawl_client import search_web

        result = await search_web("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_success(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import search_web

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"url": "https://example.com/1", "title": "Result 1", "markdown": "text"},
                {"url": "https://example.com/2", "title": "Result 2", "markdown": "text"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        results = await search_web("BTS album price", limit=5)
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"

    @pytest.mark.asyncio
    async def test_search_limit_capped_at_20(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import search_web

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        await search_web("query", limit=100)

        call_args = mock_client.post.call_args
        body = call_args.kwargs["json"]
        assert body["limit"] == 20  # capped

    @pytest.mark.asyncio
    async def test_search_rate_limited(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import search_web

        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        results = await search_web("query")
        assert results == []


class TestExtractStructured:
    """Tests for extract_structured()."""

    @pytest.mark.asyncio
    async def test_extract_returns_extracted_data(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import extract_structured

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "extract": {"title": "Funko Pop", "price": 14.99},
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        result = await extract_structured("https://example.com", schema)
        assert result is not None
        assert result["title"] == "Funko Pop"
        assert result["price"] == 14.99

    @pytest.mark.asyncio
    async def test_extract_returns_none_on_no_extract(self, monkeypatch):
        monkeypatch.setattr("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test")
        from app.lib.firecrawl_client import extract_structured

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"markdown": "just text"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        result = await extract_structured("https://example.com", {})
        assert result is None


class TestClose:
    """Tests for close()."""

    @pytest.mark.asyncio
    async def test_close_sets_client_to_none(self, monkeypatch):
        from app.lib.firecrawl_client import close

        mock_client = AsyncMock()
        mock_client.is_closed = False

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", mock_client)

        await close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self, monkeypatch):
        from app.lib.firecrawl_client import close

        monkeypatch.setattr("app.lib.firecrawl_client._http_client", None)
        await close()  # should not raise
