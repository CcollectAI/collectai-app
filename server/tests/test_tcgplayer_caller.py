"""Tests for the TCGPlayer marketplace caller.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - search() normalises catalog product + pricing
  - search() 429 → record_failure()
  - search() returns [] when circuit is OPEN
  - sold_comps() reuses search results with is_sold=True (post-refactor)
  - sold_comps() returns [] on empty search
  - _convert_usd_to_eur helper (with rates / fallback)
  - _resolve_category_id mapping
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

from workers.circuit_breaker import tcgplayer_circuit, CircuitState


@pytest.fixture(autouse=True)
def _reset_circuit():
    tcgplayer_circuit.reset()
    yield
    tcgplayer_circuit.reset()


def _fake_response(status_code: int = 200, json_body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body or {},
        request=httpx.Request("GET", "https://fake.example.com"),
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestTCGPlayerCallerConfig:

    def test_configured_false_without_token(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller

        assert TCGPlayerCaller(bearer_token="").configured is False
        assert TCGPlayerCaller(bearer_token=None).configured is False

    def test_configured_true_with_token(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller

        assert TCGPlayerCaller(bearer_token="tok").configured is True


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestTCGPlayerCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller
        return TCGPlayerCaller(bearer_token="test-bearer")

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller

        caller = TCGPlayerCaller(bearer_token="")
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_normalizes_catalog_product(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        catalog_resp = _fake_response(200, {
            "results": [{
                "productId": 12345,
                "name": "Charizard V",
                "url": "/product/12345",
                "imageUrl": "https://img.tcgplayer.com/12345.jpg",
            }]
        })
        price_resp = _fake_response(200, {
            "results": [{
                "productId": 12345,
                "marketPrice": 55.0,
                "subTypeName": "Normal",
            }]
        })
        mock_client.get = AsyncMock(side_effect=[catalog_resp, price_resp])
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Charizard", category="pokemon")

        assert len(results) == 1
        hit = results[0]
        assert hit["source"] == "tcgplayer"
        assert hit["raw_id"] == "12345"
        assert hit["title"] == "Charizard V"
        assert hit["source_price"] == 55.0
        assert hit["source_currency"] == "USD"
        assert hit["currency"] == "EUR"
        assert hit["is_sold"] is False
        assert hit["url"] == "https://www.tcgplayer.com/product/12345"
        assert hit["image_url"] == "https://img.tcgplayer.com/12345.jpg"

    @pytest.mark.asyncio
    async def test_search_429_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        rate_limited = _fake_response(429)
        mock_client.get = AsyncMock(return_value=rate_limited)
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.tcgplayer_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_circuit_open_skips(self, caller):
        """When circuit is OPEN, search() returns [] without any HTTP call."""
        for _ in range(5):
            tcgplayer_circuit.record_failure()
        assert tcgplayer_circuit.state == CircuitState.OPEN

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.search("test")

        assert result == []
        mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# sold_comps()  (post-refactor: reuses search())
# ---------------------------------------------------------------------------


class TestTCGPlayerCallerSoldComps:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller
        return TCGPlayerCaller(bearer_token="test-bearer")

    @pytest.mark.asyncio
    async def test_sold_comps_reuses_search(self, caller):
        """After refactor, sold_comps() returns search results with is_sold=True."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        catalog_resp = _fake_response(200, {
            "results": [{
                "productId": 100,
                "name": "Pikachu V",
                "url": "/product/100",
            }]
        })
        price_resp = _fake_response(200, {
            "results": [{
                "productId": 100,
                "marketPrice": 10.0,
                "subTypeName": "Normal",
            }]
        })
        mock_client.get = AsyncMock(side_effect=[catalog_resp, price_resp])
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("Pikachu", category="pokemon")

        assert len(results) == 1
        hit = results[0]
        assert hit["is_sold"] is True
        assert hit["source"] == "tcgplayer"
        assert hit["title"] == "Pikachu V"
        # Only 2 GET calls (catalog + pricing from search), not 3
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_sold_comps_empty_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        empty_resp = _fake_response(200, {"results": []})
        mock_client.get = AsyncMock(return_value=empty_resp)
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("nonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestTCGPlayerHelpers:

    def test_convert_usd_to_eur_with_rates(self):
        from app.agents.adapters.tcgplayer_caller import _convert_usd_to_eur

        result = _convert_usd_to_eur(100.0, {"USD": 0.92})
        assert result == 92.0

    def test_convert_usd_to_eur_fallback(self):
        from app.agents.adapters.tcgplayer_caller import _convert_usd_to_eur
        import app.agents.adapters.tcgplayer_caller as _mod

        # Use the module-level USD_TO_EUR that the function actually references,
        # not app.config.USD_TO_EUR which may diverge if config is reloaded.
        result = _convert_usd_to_eur(100.0)
        assert result == round(100.0 * _mod.USD_TO_EUR, 2)

    def test_resolve_category_id(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller

        caller = TCGPlayerCaller(bearer_token="tok")
        assert caller._resolve_category_id("pokemon") == 3
        assert caller._resolve_category_id("mtg") == 1
        assert caller._resolve_category_id("yugioh") == 2
        assert caller._resolve_category_id("unknown") is None
        assert caller._resolve_category_id(None) is None
