"""
Tests for app/agents/adapters/stockx_caller.py — StockX API adapter.

Covers:
  - _normalize_product() helper
  - .configured property (True / False)
  - search() empty when not configured
  - search() with mocked API response
  - search() circuit open short-circuit
  - search() handles exception / records failure
  - lookup() not configured / success / exception
  - sold_comps() filters to is_sold items
  - health_check() not configured / success
  - close() cleanup
  - Constants
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from workers.circuit_breaker import stockx_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    stockx_circuit.reset()
    yield
    stockx_circuit.reset()


def _fake_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    import json
    body = json.dumps(json_data or {}).encode()
    return httpx.Response(
        status_code=status_code,
        content=body,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://api.stockx.com/v2/catalog/search"),
    )


# ---------------------------------------------------------------------------
# _normalize_product helper
# ---------------------------------------------------------------------------

class TestNormalizeProduct:
    def test_basic_normalization(self):
        from app.agents.adapters.stockx_caller import _normalize_product

        product = {
            "id": "abc123",
            "urlKey": "nike-dunk-low-panda",
            "title": "Nike Dunk Low Panda",
            "brand": "Nike",
            "attributes": {"retailPrice": 110, "releaseDate": "2021-03-10", "brand": "Nike"},
            "market": {"lastSale": 180, "lowestAsk": 185, "highestBid": 175},
            "media": {"thumbUrl": "https://stockx.com/thumb.jpg", "imageUrl": "https://stockx.com/full.jpg"},
        }
        hit = _normalize_product(product)

        assert hit["source"] == "stockx"
        assert hit["raw_id"] == "stockx-abc123"
        assert hit["title"] == "Nike Dunk Low Panda"
        assert hit["price"] == 180.0
        assert hit["currency"] == "USD"
        assert hit["source_price"] == 180.0
        assert hit["source_currency"] == "USD"
        assert hit["url"] == "https://stockx.com/nike-dunk-low-panda"
        assert hit["condition"] == "New"
        assert hit["image_url"] == "https://stockx.com/thumb.jpg"
        assert hit["is_sold"] is False
        assert hit["last_sale"] == 180.0
        assert hit["lowest_ask"] == 185.0
        assert hit["highest_bid"] == 175.0
        assert hit["retail_price"] == 110.0
        assert hit["release_date"] == "2021-03-10"
        assert hit["brand"] == "Nike"

    def test_falls_back_to_lowest_ask_when_no_last_sale(self):
        from app.agents.adapters.stockx_caller import _normalize_product

        product = {
            "id": "x1",
            "title": "Test",
            "market": {"lastSale": 0, "lowestAsk": 99, "highestBid": 0},
        }
        hit = _normalize_product(product)
        assert hit["price"] == 99.0
        assert hit["last_sale"] is None
        assert hit["lowest_ask"] == 99.0

    def test_uses_salesinformation_alias(self):
        from app.agents.adapters.stockx_caller import _normalize_product

        product = {
            "id": "x2",
            "title": "Alias",
            "salesInformation": {"lastSalePrice": 42, "lowestAskPrice": 50, "highestBidPrice": 40},
        }
        hit = _normalize_product(product)
        assert hit["price"] == 42.0
        assert hit["last_sale"] == 42.0
        assert hit["lowest_ask"] == 50.0
        assert hit["highest_bid"] == 40.0

    def test_empty_product(self):
        from app.agents.adapters.stockx_caller import _normalize_product

        hit = _normalize_product({})
        assert hit["source"] == "stockx"
        assert hit["title"] == "Unknown"
        assert hit["price"] == 0.0
        assert hit["raw_id"] == "stockx-"
        assert hit["last_sale"] is None
        assert hit["lowest_ask"] is None
        assert hit["retail_price"] is None

    def test_url_uses_urlkey_preferred_over_id(self):
        from app.agents.adapters.stockx_caller import _normalize_product

        product = {"id": "xxx", "urlKey": "slug-here", "title": "T"}
        hit = _normalize_product(product)
        assert hit["url"] == "https://stockx.com/slug-here"


# ---------------------------------------------------------------------------
# StockXCaller
# ---------------------------------------------------------------------------

class TestStockXCaller:
    def test_configured_true_with_key(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        caller = StockXCaller(api_key="test-key")
        assert caller.configured is True

    def test_configured_false_without_key(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        caller = StockXCaller(api_key="")
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_empty_when_not_configured(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        caller = StockXCaller(api_key="")
        assert await caller.search("nike") == []

    @pytest.mark.asyncio
    async def test_search_success(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        payload = {
            "products": [
                {"id": "p1", "urlKey": "p-one", "title": "Product One",
                 "market": {"lastSale": 100, "lowestAsk": 110, "highestBid": 95}},
                {"id": "p2", "urlKey": "p-two", "title": "Product Two",
                 "market": {"lastSale": 0, "lowestAsk": 50, "highestBid": 45}},
            ]
        }

        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, payload))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("test", limit=10)
        assert len(results) == 2
        assert results[0]["source"] == "stockx"
        assert results[0]["price"] == 100.0
        assert results[1]["price"] == 50.0
        assert stockx_circuit._failure_count == 0

    @pytest.mark.asyncio
    async def test_search_handles_results_alias(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        payload = {"results": [{"id": "r1", "title": "R", "market": {"lastSale": 10}}]}
        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, payload))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("x")
        assert len(results) == 1
        assert results[0]["raw_id"] == "stockx-r1"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        payload = {"products": [
            {"id": f"p{i}", "title": f"P{i}", "market": {"lastSale": i + 1}}
            for i in range(20)
        ]}
        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, payload))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("x", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("network"))
        mock_client.is_closed = False
        caller._http = mock_client

        assert await caller.search("x") == []
        assert stockx_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_http_error_records_failure(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        resp = httpx.Response(
            status_code=500,
            content=b"{}",
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "https://api.stockx.com/v2/catalog/search"),
        )
        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        caller._http = mock_client

        assert await caller.search("x") == []
        assert stockx_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_search_circuit_open_skips(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        for _ in range(6):
            stockx_circuit.record_failure()

        caller = StockXCaller(api_key="key")
        assert await caller.search("x") == []

    @pytest.mark.asyncio
    async def test_lookup_not_configured(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        caller = StockXCaller(api_key="")
        assert await caller.lookup("id") is None

    @pytest.mark.asyncio
    async def test_lookup_success(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        payload = {"product": {"id": "abc", "title": "Foo", "market": {"lastSale": 77}}}
        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, payload))
        mock_client.is_closed = False
        caller._http = mock_client

        hit = await caller.lookup("abc")
        assert hit is not None
        assert hit["raw_id"] == "stockx-abc"
        assert hit["price"] == 77.0

    @pytest.mark.asyncio
    async def test_lookup_handles_exception(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("boom"))
        mock_client.is_closed = False
        caller._http = mock_client

        assert await caller.lookup("abc") is None
        assert stockx_circuit._failure_count >= 1

    @pytest.mark.asyncio
    async def test_lookup_circuit_open(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        for _ in range(6):
            stockx_circuit.record_failure()

        caller = StockXCaller(api_key="key")
        assert await caller.lookup("abc") is None

    @pytest.mark.asyncio
    async def test_sold_comps_filters_to_sold_only(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        payload = {"products": [
            {"id": "has-sale", "title": "Has Sale", "market": {"lastSale": 200, "lowestAsk": 210}},
            {"id": "no-sale", "title": "No Sale", "market": {"lastSale": 0, "lowestAsk": 50}},
        ]}
        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, payload))
        mock_client.is_closed = False
        caller._http = mock_client

        sold = await caller.sold_comps("x")
        assert len(sold) == 1
        assert sold[0]["raw_id"] == "stockx-has-sale"
        assert sold[0]["is_sold"] is True
        assert sold[0]["price"] == 200.0
        assert sold[0]["source_price"] == 200.0

    @pytest.mark.asyncio
    async def test_sold_comps_empty_when_not_configured(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        caller = StockXCaller(api_key="")
        assert await caller.sold_comps("x") == []

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.stockx_caller import StockXCaller
        caller = StockXCaller(api_key="")
        assert await caller.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_fake_response(200, {"products": []}))
        mock_client.is_closed = False
        caller._http = mock_client

        assert await caller.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        resp = httpx.Response(
            status_code=401,
            content=b"{}",
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "https://api.stockx.com/v2/catalog/search"),
        )
        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        caller._http = mock_client

        assert await caller.health_check() is False

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_already_closed(self):
        from app.agents.adapters.stockx_caller import StockXCaller

        caller = StockXCaller(api_key="key")
        mock_client = AsyncMock()
        mock_client.is_closed = True
        mock_client.aclose = AsyncMock()
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_not_called()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_reliability_value(self):
        from app.agents.adapters.stockx_caller import STOCKX_SOURCE_RELIABILITY
        assert STOCKX_SOURCE_RELIABILITY == 0.85

    def test_base_url(self):
        from app.agents.adapters.stockx_caller import STOCKX_BASE, STOCKX_BROWSE
        assert "api.stockx.com" in STOCKX_BASE
        assert "catalog/search" in STOCKX_BROWSE

    def test_supported_categories(self):
        from app.agents.adapters.stockx_caller import SUPPORTED_CATEGORIES
        assert "designer_toys" in SUPPORTED_CATEGORIES
        assert "funko" in SUPPORTED_CATEGORIES
        assert len(SUPPORTED_CATEGORIES) >= 5
