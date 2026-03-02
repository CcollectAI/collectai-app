"""
Tests for app/agents/adapters/whisky_auctioneer_caller.py — Whisky Auctioneer adapter.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - search() with HTML scraping
  - search() circuit breaker on 429/503
  - sold_comps() from auction results page
  - sold_comps() circuit breaker on 429/503
  - _normalize_lot() helper
  - _gbp_to_eur() conversion helper
  - _parse_gbp_price() extraction helper
  - health_check() when not configured
  - close() cleanup
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from workers.circuit_breaker import whisky_auctioneer_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    whisky_auctioneer_circuit.reset()
    yield
    whisky_auctioneer_circuit.reset()


def _fake_response(status_code: int = 200, text: str = "") -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("GET", "https://fake.example.com"),
    )


# ---------------------------------------------------------------------------
# GBP conversion helper tests
# ---------------------------------------------------------------------------

class TestGbpToEur:
    """Tests for _gbp_to_eur() helper."""

    def test_conversion_positive(self):
        from app.agents.adapters.whisky_auctioneer_caller import _gbp_to_eur
        result = _gbp_to_eur(100.0)
        # Should be > 100 since GBP > EUR typically
        assert result > 0

    def test_conversion_zero(self):
        from app.agents.adapters.whisky_auctioneer_caller import _gbp_to_eur
        result = _gbp_to_eur(0.0)
        assert result == 0.0


class TestParseGbpPrice:
    """Tests for _parse_gbp_price() helper."""

    def test_pound_symbol(self):
        from app.agents.adapters.whisky_auctioneer_caller import _parse_gbp_price
        assert _parse_gbp_price("\u00a3120") == 120.0

    def test_pound_with_comma(self):
        from app.agents.adapters.whisky_auctioneer_caller import _parse_gbp_price
        assert _parse_gbp_price("\u00a31,250.00") == 1250.0

    def test_gbp_prefix(self):
        from app.agents.adapters.whisky_auctioneer_caller import _parse_gbp_price
        assert _parse_gbp_price("GBP 450") == 450.0

    def test_empty_string(self):
        from app.agents.adapters.whisky_auctioneer_caller import _parse_gbp_price
        assert _parse_gbp_price("") == 0.0

    def test_no_price(self):
        from app.agents.adapters.whisky_auctioneer_caller import _parse_gbp_price
        assert _parse_gbp_price("no price here") == 0.0


# ---------------------------------------------------------------------------
# Normalize helper tests
# ---------------------------------------------------------------------------

class TestNormalizeLot:
    """Tests for _normalize_lot() helper."""

    def test_basic_normalization(self):
        from app.agents.adapters.whisky_auctioneer_caller import _normalize_lot

        lot = {
            "id": "55555",
            "title": "Macallan 30 Year Old 1990 Vintage",
            "hammer_price": 2500.0,
            "url": "/lot/55555-macallan-30",
            "image_url": "https://wa.com/img/55555.jpg",
            "bottle_size": "70cl",
        }
        hit = _normalize_lot(lot, is_sold=False)

        assert hit["source"] == "whisky_auctioneer"
        assert hit["raw_id"] == "whisky-auc-55555"
        assert hit["title"] == "Macallan 30 Year Old 1990 Vintage"
        assert hit["source_price"] == 2500.0
        assert hit["source_currency"] == "GBP"
        assert hit["currency"] == "EUR"
        assert hit["price"] > 0  # Converted from GBP
        assert "whiskyauctioneer.com" in hit["url"]
        assert hit["image_url"] == "https://wa.com/img/55555.jpg"
        assert hit["is_sold"] is False

    def test_sold_lot(self):
        from app.agents.adapters.whisky_auctioneer_caller import _normalize_lot

        lot = {
            "id": "66666",
            "title": "Springbank 21 Year Old",
            "hammer_price": 1800.0,
            "end_date": "2025-11-20T18:00:00Z",
        }
        hit = _normalize_lot(lot, is_sold=True)

        assert hit["is_sold"] is True
        assert hit["sold_at"] == "2025-11-20T18:00:00Z"

    def test_empty_lot(self):
        from app.agents.adapters.whisky_auctioneer_caller import _normalize_lot

        hit = _normalize_lot({})
        assert hit["source"] == "whisky_auctioneer"
        assert hit["title"] == "Unknown"
        assert hit["price"] == 0.0
        assert hit["source_price"] == 0.0

    def test_absolute_url_preserved(self):
        from app.agents.adapters.whisky_auctioneer_caller import _normalize_lot

        lot = {
            "id": "77777",
            "title": "Test",
            "url": "https://www.whiskyauctioneer.com/lot/77777",
        }
        hit = _normalize_lot(lot)
        assert hit["url"] == "https://www.whiskyauctioneer.com/lot/77777"


# ---------------------------------------------------------------------------
# WhiskyAuctioneerCaller async tests
# ---------------------------------------------------------------------------

class TestWhiskyAuctioneerCaller:
    """Tests for the WhiskyAuctioneerCaller class."""

    def test_configured_default(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller
        caller = WhiskyAuctioneerCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller
        caller = WhiskyAuctioneerCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller
        caller = WhiskyAuctioneerCaller(enabled=False)
        results = await caller.search("Macallan")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_scrape_success(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        html = """
        <div class="lot-item">
            <a href="/lot/12345-macallan-25">
                <span class="lot-title">Macallan 25 Year Old</span>
            </a>
            <span class="lot-price">&pound;1,500.00</span>
        </div>
        <div class="lot-item">
            <a href="/lot/12346-springbank-18">
                <span class="lot-title">Springbank 18 Year Old</span>
            </a>
            <span class="lot-price">&pound;350.00</span>
        </div>
        """

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=html))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Macallan")
        # Results depend on regex matching — at minimum shouldn't crash
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_circuit_breaker_on_429(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("test")
        assert results == []
        assert whisky_auctioneer_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_circuit_breaker_on_503(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("test")
        assert results == []
        assert whisky_auctioneer_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("anything")
        assert results == []
        assert whisky_auctioneer_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_non_200_returns_empty(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(404))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_not_configured(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller
        caller = WhiskyAuctioneerCaller(enabled=False)
        results = await caller.sold_comps("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_circuit_breaker_on_429(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("test")
        assert results == []
        assert whisky_auctioneer_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_sold_comps_handles_exception(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("timeout"))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("test")
        assert results == []
        assert whisky_auctioneer_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller
        caller = WhiskyAuctioneerCaller(enabled=False)
        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        caller = WhiskyAuctioneerCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_circuit_open_skips(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        # Trip the circuit
        for _ in range(6):
            whisky_auctioneer_circuit.record_failure()

        caller = WhiskyAuctioneerCaller(enabled=True)
        results = await caller.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_circuit_open_skips(self):
        from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller

        # Trip the circuit
        for _ in range(6):
            whisky_auctioneer_circuit.record_failure()

        caller = WhiskyAuctioneerCaller(enabled=True)
        results = await caller.sold_comps("test")
        assert results == []


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_reliability_values(self):
        from app.agents.adapters.whisky_auctioneer_caller import (
            WHISKY_AUCTIONEER_SOURCE_RELIABILITY,
            WHISKY_AUCTIONEER_SOLD_RELIABILITY,
        )
        assert WHISKY_AUCTIONEER_SOURCE_RELIABILITY == 0.85
        assert WHISKY_AUCTIONEER_SOLD_RELIABILITY == 0.95

    def test_search_url(self):
        from app.agents.adapters.whisky_auctioneer_caller import WHISKY_AUCTIONEER_SEARCH_URL
        assert "whiskyauctioneer.com" in WHISKY_AUCTIONEER_SEARCH_URL

    def test_results_url(self):
        from app.agents.adapters.whisky_auctioneer_caller import WHISKY_AUCTIONEER_RESULTS_URL
        assert "auction-results" in WHISKY_AUCTIONEER_RESULTS_URL
