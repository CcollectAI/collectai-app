"""
Tests for Layer 2 marketplace adapters: Mercari US, WhatNot, Vinted, Mavin.

Covers:
  - Configured/unconfigured state
  - Search returns list on success and on error
  - Circuit breaker integration
  - Close cleanup
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")


def _make_mock_client(response):
    """Create a mock httpx.AsyncClient with a response for get()."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.aclose = AsyncMock()
    mock_client.is_closed = False
    return mock_client


def _make_response(status_code=200, json_data=None, text=""):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# MercariUSCaller
# ---------------------------------------------------------------------------


class TestMercariUSCaller:
    """Tests for MercariUSCaller."""

    def test_configured_when_enabled(self):
        from app.agents.adapters.mercari_us_caller import MercariUSCaller
        caller = MercariUSCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured_when_disabled(self):
        from app.agents.adapters.mercari_us_caller import MercariUSCaller
        caller = MercariUSCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_disabled_returns_empty(self):
        from app.agents.adapters.mercari_us_caller import MercariUSCaller
        caller = MercariUSCaller(enabled=False)
        results = await caller.search("Charizard")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        from app.agents.adapters.mercari_us_caller import MercariUSCaller

        resp = _make_response(200, {"items": []})
        mock_client = _make_mock_client(resp)

        caller = MercariUSCaller(enabled=True)
        caller._http = mock_client
        results = await caller.search("Charizard")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_circuit_open_returns_empty(self):
        from app.agents.adapters.mercari_us_caller import MercariUSCaller
        from workers.circuit_breaker import CircuitOpenError

        caller = MercariUSCaller(enabled=True)
        with patch("app.agents.adapters.mercari_us_caller.mercari_us_circuit") as mock_cb:
            mock_cb.check.side_effect = CircuitOpenError("mercari_us", 60.0)
            results = await caller.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.mercari_us_caller import MercariUSCaller
        caller = MercariUSCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.is_closed = False
        caller._http = mock_client
        await caller.close()
        mock_client.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# WhatNotCaller
# ---------------------------------------------------------------------------


class TestWhatNotCaller:
    """Tests for WhatNotCaller."""

    def test_configured_when_enabled(self):
        from app.agents.adapters.whatnot_caller import WhatNotCaller
        caller = WhatNotCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured_when_disabled(self):
        from app.agents.adapters.whatnot_caller import WhatNotCaller
        caller = WhatNotCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_disabled_returns_empty(self):
        from app.agents.adapters.whatnot_caller import WhatNotCaller
        caller = WhatNotCaller(enabled=False)
        results = await caller.search("Pikachu")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        from app.agents.adapters.whatnot_caller import WhatNotCaller

        resp = _make_response(200, text="<html><body></body></html>")
        mock_client = _make_mock_client(resp)

        caller = WhatNotCaller(enabled=True)
        caller._http = mock_client
        results = await caller.search("Pikachu")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_circuit_open_returns_empty(self):
        from app.agents.adapters.whatnot_caller import WhatNotCaller
        from workers.circuit_breaker import CircuitOpenError

        caller = WhatNotCaller(enabled=True)
        with patch("app.agents.adapters.whatnot_caller.whatnot_circuit") as mock_cb:
            mock_cb.check.side_effect = CircuitOpenError("whatnot", 60.0)
            results = await caller.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.whatnot_caller import WhatNotCaller
        caller = WhatNotCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.is_closed = False
        caller._http = mock_client
        await caller.close()
        mock_client.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# VintedCaller
# ---------------------------------------------------------------------------


class TestVintedCaller:
    """Tests for VintedCaller."""

    def test_configured_when_enabled(self):
        from app.agents.adapters.vinted_caller import VintedCaller
        caller = VintedCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured_when_disabled(self):
        from app.agents.adapters.vinted_caller import VintedCaller
        caller = VintedCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_disabled_returns_empty(self):
        from app.agents.adapters.vinted_caller import VintedCaller
        caller = VintedCaller(enabled=False)
        results = await caller.search("Funko Pop")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        from app.agents.adapters.vinted_caller import VintedCaller

        resp = _make_response(200, {"items": []})
        mock_client = _make_mock_client(resp)

        caller = VintedCaller(enabled=True)
        caller._http = mock_client
        results = await caller.search("Funko Pop")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_circuit_open_returns_empty(self):
        from app.agents.adapters.vinted_caller import VintedCaller
        from workers.circuit_breaker import CircuitOpenError

        caller = VintedCaller(enabled=True)
        with patch("app.agents.adapters.vinted_caller.vinted_circuit") as mock_cb:
            mock_cb.check.side_effect = CircuitOpenError("vinted", 60.0)
            results = await caller.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.vinted_caller import VintedCaller
        caller = VintedCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.is_closed = False
        caller._http = mock_client
        await caller.close()
        mock_client.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# MavinCaller
# ---------------------------------------------------------------------------


class TestMavinCaller:
    """Tests for MavinCaller."""

    def test_configured_with_api_key(self):
        from app.agents.adapters.mavin_caller import MavinCaller
        caller = MavinCaller(api_key="test-key", enabled=True)
        assert caller.configured is True

    def test_configured_without_api_key_still_works(self):
        """Mavin works without API key (HTML scraping fallback)."""
        from app.agents.adapters.mavin_caller import MavinCaller
        caller = MavinCaller(api_key=None, enabled=True)
        assert caller.configured is True

    def test_not_configured_when_disabled(self):
        from app.agents.adapters.mavin_caller import MavinCaller
        caller = MavinCaller(api_key="test-key", enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_disabled_returns_empty(self):
        from app.agents.adapters.mavin_caller import MavinCaller
        caller = MavinCaller(api_key="test-key", enabled=False)
        results = await caller.search("Charizard Base Set")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        from app.agents.adapters.mavin_caller import MavinCaller

        resp = _make_response(200, {"results": []}, text="<html></html>")
        mock_client = _make_mock_client(resp)

        caller = MavinCaller(api_key="test-key", enabled=True)
        caller._http = mock_client
        results = await caller.search("Charizard Base Set")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_circuit_open_returns_empty(self):
        from app.agents.adapters.mavin_caller import MavinCaller
        from workers.circuit_breaker import CircuitOpenError

        caller = MavinCaller(api_key="test-key", enabled=True)
        with patch("app.agents.adapters.mavin_caller.mavin_circuit") as mock_cb:
            mock_cb.check.side_effect = CircuitOpenError("mavin", 60.0)
            results = await caller.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.mavin_caller import MavinCaller
        caller = MavinCaller(api_key="test-key", enabled=True)
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_client.is_closed = False
        caller._http = mock_client
        await caller.close()
        mock_client.aclose.assert_called_once()
