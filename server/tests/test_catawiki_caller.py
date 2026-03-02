"""
Tests for app/agents/adapters/catawiki_caller.py — Catawiki marketplace adapter.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - search() with JSON API response
  - search() fallback to scraping on non-200
  - search() circuit breaker on 429/503
  - sold_comps() with closed status results
  - sold_comps() circuit breaker on 429/503
  - _normalize_lot() helper
  - health_check() when not configured
  - close() cleanup
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from workers.circuit_breaker import catawiki_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    catawiki_circuit.reset()
    yield
    catawiki_circuit.reset()


def _fake_response(status_code: int = 200, json_body: dict | None = None, text: str = "") -> httpx.Response:
    if json_body is not None:
        resp = httpx.Response(
            status_code=status_code,
            json=json_body,
            request=httpx.Request("GET", "https://fake.example.com"),
        )
    else:
        resp = httpx.Response(
            status_code=status_code,
            text=text,
            request=httpx.Request("GET", "https://fake.example.com"),
        )
    return resp


# ---------------------------------------------------------------------------
# Normalize helper tests
# ---------------------------------------------------------------------------

class TestNormalizeLot:
    """Tests for _normalize_lot() helper."""

    def test_basic_normalization(self):
        from app.agents.adapters.catawiki_caller import _normalize_lot

        lot = {
            "id": "12345",
            "title": "Macallan 25 Year Old Sherry Cask",
            "current_bid": 450.0,
            "slug": "macallan-25-year",
            "images": [{"url": "https://img.catawiki.com/12345.jpg"}],
            "condition": "Excellent",
        }
        hit = _normalize_lot(lot, is_sold=False)

        assert hit["source"] == "catawiki"
        assert hit["raw_id"] == "catawiki-12345"
        assert hit["title"] == "Macallan 25 Year Old Sherry Cask"
        assert hit["price"] == 450.0
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "EUR"
        assert "catawiki.com" in hit["url"]
        assert hit["image_url"] == "https://img.catawiki.com/12345.jpg"
        assert hit["condition"] == "Excellent"
        assert hit["is_sold"] is False

    def test_sold_lot_normalization(self):
        from app.agents.adapters.catawiki_caller import _normalize_lot

        lot = {
            "id": "67890",
            "title": "Rolex Submariner 1680",
            "hammer_price": 12500.0,
            "slug": "rolex-submariner",
            "closed_at": "2025-12-01T14:00:00Z",
        }
        hit = _normalize_lot(lot, is_sold=True)

        assert hit["raw_id"] == "catawiki-67890"
        assert hit["price"] == 12500.0
        assert hit["is_sold"] is True
        assert hit["sold_at"] == "2025-12-01T14:00:00Z"

    def test_empty_lot(self):
        from app.agents.adapters.catawiki_caller import _normalize_lot

        hit = _normalize_lot({})
        assert hit["source"] == "catawiki"
        assert hit["title"] == "Unknown"
        assert hit["price"] == 0.0

    def test_estimate_fields(self):
        from app.agents.adapters.catawiki_caller import _normalize_lot

        lot = {
            "id": "111",
            "title": "Test Lot",
            "estimate_min": 100.0,
            "estimate_max": 200.0,
        }
        hit = _normalize_lot(lot)
        assert hit["estimate_min"] == 100.0
        assert hit["estimate_max"] == 200.0


# ---------------------------------------------------------------------------
# CatawikiCaller async tests
# ---------------------------------------------------------------------------

class TestCatawikiCaller:
    """Tests for the CatawikiCaller class."""

    def test_configured_default(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller
        caller = CatawikiCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller
        caller = CatawikiCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller
        caller = CatawikiCaller(enabled=False)
        results = await caller.search("Macallan whisky")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_json_api_success(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        api_response = _fake_response(200, json_body={
            "lots": [
                {
                    "id": "100",
                    "title": "Macallan 18 Year Old",
                    "current_bid": 350.0,
                    "slug": "macallan-18",
                    "images": [{"url": "https://img.catawiki.com/100.jpg"}],
                },
                {
                    "id": "101",
                    "title": "Macallan 25 Year Old",
                    "current_bid": 800.0,
                    "slug": "macallan-25",
                    "images": [],
                },
            ]
        })

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=api_response)
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Macallan")

        assert len(results) == 2
        assert results[0]["source"] == "catawiki"
        assert results[0]["raw_id"] == "catawiki-100"
        assert results[0]["price"] == 350.0
        assert results[0]["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_search_circuit_breaker_on_429(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("test")
        assert results == []
        # Circuit breaker should have recorded a failure
        assert catawiki_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_circuit_breaker_on_503(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("test")
        assert results == []
        assert catawiki_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("network error"))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("anything")
        assert results == []
        assert catawiki_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_sold_comps_success(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        api_response = _fake_response(200, json_body={
            "lots": [
                {
                    "id": "200",
                    "title": "Leica M6 TTL",
                    "hammer_price": 2800.0,
                    "slug": "leica-m6-ttl",
                    "closed_at": "2025-11-15T10:00:00Z",
                },
            ]
        })

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=api_response)
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("Leica M6")

        assert len(results) == 1
        assert results[0]["is_sold"] is True
        assert results[0]["price"] == 2800.0
        assert results[0]["sold_at"] == "2025-11-15T10:00:00Z"

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_not_configured(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller
        caller = CatawikiCaller(enabled=False)
        results = await caller.sold_comps("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_circuit_breaker_on_429(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("test")
        assert results == []
        assert catawiki_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller
        caller = CatawikiCaller(enabled=False)
        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        caller = CatawikiCaller(enabled=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_circuit_open_skips(self):
        from app.agents.adapters.catawiki_caller import CatawikiCaller

        # Trip the circuit
        for _ in range(6):
            catawiki_circuit.record_failure()

        caller = CatawikiCaller(enabled=True)
        results = await caller.search("test")
        assert results == []


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_reliability_values(self):
        from app.agents.adapters.catawiki_caller import (
            CATAWIKI_SOURCE_RELIABILITY,
            CATAWIKI_SOLD_RELIABILITY,
        )
        assert CATAWIKI_SOURCE_RELIABILITY == 0.80
        assert CATAWIKI_SOLD_RELIABILITY == 0.90

    def test_api_url(self):
        from app.agents.adapters.catawiki_caller import CATAWIKI_API_URL
        assert "catawiki.com" in CATAWIKI_API_URL
        assert "buyer/api" in CATAWIKI_API_URL
