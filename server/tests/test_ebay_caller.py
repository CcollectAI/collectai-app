"""Tests for the eBay marketplace caller.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - OAuth token caching and expiry refresh
  - Browse API response normalisation
  - 429 → record_failure() in search()
  - Finding API response normalisation (sold_comps)
  - 429 → record_failure() in sold_comps()
  - _convert_price helper (USD→EUR, EUR passthrough)
"""

from __future__ import annotations

import os
import sys
import time
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

from workers.circuit_breaker import ebay_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    ebay_circuit.reset()
    yield
    ebay_circuit.reset()


@pytest.fixture(autouse=True)
def _clear_token_cache():
    """Reset the module-level OAuth token cache between tests."""
    from app.agents.adapters.ebay_caller import _token_cache
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0
    yield
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0


def _fake_response(status_code: int = 200, json_body: dict | None = None, headers: dict | None = None) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_body or {},
        request=httpx.Request("GET", "https://fake.example.com"),
    )
    if headers:
        resp.headers.update(headers)
    return resp


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestEbayCallerConfig:

    def test_configured_false_when_missing_credentials(self):
        from app.agents.adapters.ebay_caller import EbayCaller

        assert EbayCaller(client_id="", client_secret="").configured is False
        assert EbayCaller(client_id="id", client_secret="").configured is False
        assert EbayCaller(client_id="", client_secret="sec").configured is False

    def test_configured_true_when_credentials_set(self):
        from app.agents.adapters.ebay_caller import EbayCaller

        caller = EbayCaller(client_id="id", client_secret="sec")
        assert caller.configured is True


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestEbayCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.ebay_caller import EbayCaller
        return EbayCaller(client_id="test-id", client_secret="test-secret")

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.ebay_caller import EbayCaller

        caller = EbayCaller(client_id="", client_secret="")
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_oauth_token_cached(self, caller):
        """Two search() calls should reuse the same OAuth token (1 POST)."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 7200})
        browse_resp = _fake_response(200, {"itemSummaries": []})
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=browse_resp)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.search("query1")
        await caller.search("query2")

        # OAuth POST should only be called once — token is cached
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_oauth_token_refresh_on_expiry(self, caller):
        """When the cached token expires, a new one should be fetched."""
        from app.agents.adapters.ebay_caller import _token_cache

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        oauth_resp = _fake_response(200, {"access_token": "tok-new", "expires_in": 7200})
        browse_resp = _fake_response(200, {"itemSummaries": []})
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=browse_resp)
        mock_client.is_closed = False
        caller._http = mock_client

        # Seed an expired token
        _token_cache["token"] = "tok-old"
        _token_cache["expires_at"] = time.time() - 100

        await caller.search("query")

        # Should have called POST to refresh
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_search_normalizes_browse_item(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 7200})
        browse_resp = _fake_response(200, {
            "itemSummaries": [{
                "itemId": "v1|12345",
                "title": "Charizard VMAX",
                "price": {"value": "100.00", "currency": "USD"},
                "condition": "New",
                "itemWebUrl": "https://ebay.com/itm/12345",
                "image": {"imageUrl": "https://img.ebay.com/12345.jpg"},
            }]
        })
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=browse_resp)
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Charizard")

        assert len(results) == 1
        hit = results[0]
        assert hit["source"] == "ebay"
        assert hit["raw_id"] == "v1|12345"
        assert hit["title"] == "Charizard VMAX"
        assert hit["is_sold"] is False
        assert hit["source_price"] == 100.0
        assert hit["source_currency"] == "USD"
        assert hit["url"] == "https://ebay.com/itm/12345"
        assert hit["image_url"] == "https://img.ebay.com/12345.jpg"

    @pytest.mark.asyncio
    async def test_search_429_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 7200})
        rate_limited = _fake_response(429)
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=rate_limited)
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.ebay_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestEbayCallerSoldComps:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.ebay_caller import EbayCaller
        return EbayCaller(client_id="test-id", client_secret="test-secret")

    @pytest.mark.asyncio
    async def test_sold_comps_normalizes_finding_item(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        finding_resp = _fake_response(200, {
            "findCompletedItemsResponse": [{
                "searchResult": [{
                    "item": [{
                        "itemId": ["999"],
                        "title": ["Sold Card"],
                        "sellingStatus": [{"currentPrice": [{"__value__": "50.0", "@currencyId": "USD"}]}],
                        "listingInfo": [{"endTime": ["2026-01-15T12:00:00Z"]}],
                        "condition": [{"conditionDisplayName": ["Used"]}],
                        "galleryURL": ["https://img.ebay.com/999.jpg"],
                        "viewItemURL": ["https://ebay.com/itm/999"],
                    }]
                }]
            }]
        })
        mock_client.get = AsyncMock(return_value=finding_resp)
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("Sold Card")

        assert len(results) == 1
        hit = results[0]
        assert hit["source"] == "ebay"
        assert hit["is_sold"] is True
        assert hit["raw_id"] == "999"
        assert hit["title"] == "Sold Card"
        assert hit["sold_at"] == "2026-01-15T12:00:00Z"
        assert hit["condition"] == "Used"
        assert hit["source_price"] == 50.0
        assert hit["source_currency"] == "USD"

    @pytest.mark.asyncio
    async def test_sold_comps_429_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        rate_limited = _fake_response(429)
        mock_client.get = AsyncMock(return_value=rate_limited)
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.ebay_circuit.record_failure") as mock_fail:
            result = await caller.sold_comps("test")

        mock_fail.assert_called_once()
        assert result == []


# ---------------------------------------------------------------------------
# _convert_price helper
# ---------------------------------------------------------------------------


class TestConvertPrice:

    def test_convert_price_usd_to_eur(self):
        from app.agents.adapters.ebay_caller import _convert_price

        result = _convert_price(100, "USD", {"USD": 0.92})
        assert result["price"] == 92.0
        assert result["currency"] == "EUR"
        assert result["source_price"] == 100
        assert result["source_currency"] == "USD"

    def test_convert_price_eur_passthrough(self):
        from app.agents.adapters.ebay_caller import _convert_price

        result = _convert_price(50, "EUR")
        assert result["price"] == 50
        assert result["currency"] == "EUR"
        assert result["source_price"] == 50
        assert result["source_currency"] == "EUR"
