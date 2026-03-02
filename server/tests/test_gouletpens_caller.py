"""Tests for the GouletPens marketplace caller.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - search() returns empty on circuit open
  - search() HTML parsing / normalisation
  - search() non-200 records failure
  - search() network exception records failure
  - sold_comps() always returns empty list
  - health_check() returns True on 200
  - health_check() returns False when not configured
  - close() closes HTTP client
  - _parse_price helper
  - _normalize_listing helper
  - Circuit breaker integration
  - Region config integration
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

from workers.circuit_breaker import gouletpens_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    gouletpens_circuit.reset()
    yield
    gouletpens_circuit.reset()


def _fake_response(status_code: int = 200, text: str = "", headers: dict | None = None) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("GET", "https://fake.example.com"),
    )
    if headers:
        resp.headers.update(headers)
    return resp


# ---------------------------------------------------------------------------
# Sample HTML for parsing tests
# ---------------------------------------------------------------------------

SAMPLE_GOULET_HTML = """
<html>
<body>
<div class="product-grid">
  <a href="/products/pilot-vanishing-point-fountain-pen" data-sku="PIL-VP-BLK">
    <div class="product_title">Pilot Vanishing Point Fountain Pen - Black</div>
    <img src="https://cdn.shopify.com/s/files/1/0012/goulet/pilot-vp.jpg" />
    <span class="price">$185.00</span>
  </a>
</div>
<div class="product-grid">
  <a href="/products/lamy-safari-fountain-pen" data-sku="LAMY-SAFARI-BLU">
    <div class="product_title">Lamy Safari Fountain Pen - Blue</div>
    <img src="https://cdn.shopify.com/s/files/1/0012/goulet/lamy-safari.jpg" />
    <span class="price">$29.60</span>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestGouletPensCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestGouletPensCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller
        return GouletPensCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        for _ in range(10):
            gouletpens_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_GOULET_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("pilot")

        assert len(results) >= 1
        hit = results[0]
        assert hit["source"] == "gouletpens"
        assert hit["raw_id"].startswith("goulet-")
        assert hit["currency"] == "USD"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert hit["condition"] == "New"

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.gouletpens_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.gouletpens_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.gouletpens_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestGouletPensCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestGouletPensCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestGouletPensCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.gouletpens_caller import GouletPensCaller

        caller = GouletPensCaller(enabled=True)
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_parse_price_dollar_sign(self):
        from app.agents.adapters.gouletpens_caller import _parse_price

        assert _parse_price("$185.00") == 185.00

    def test_parse_price_no_symbol(self):
        from app.agents.adapters.gouletpens_caller import _parse_price

        assert _parse_price("29.60") == 29.60

    def test_parse_price_with_commas(self):
        from app.agents.adapters.gouletpens_caller import _parse_price

        assert _parse_price("$1,200.00") == 1200.00

    def test_parse_price_empty(self):
        from app.agents.adapters.gouletpens_caller import _parse_price

        assert _parse_price("") == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.gouletpens_caller import _normalize_listing

        hit = _normalize_listing(
            sku="PIL-VP-BLK",
            title="Pilot Vanishing Point Fountain Pen - Black",
            price=185.00,
            image_url="https://cdn.shopify.com/goulet/pilot-vp.jpg",
            url="https://www.gouletpens.com/products/pilot-vanishing-point-fountain-pen",
        )

        assert hit["source"] == "gouletpens"
        assert hit["raw_id"] == "goulet-PIL-VP-BLK"
        assert hit["title"] == "Pilot Vanishing Point Fountain Pen - Black"
        assert hit["price"] == 185.00
        assert hit["currency"] == "USD"
        assert hit["condition"] == "New"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "gouletpens.com" in hit["url"]

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.gouletpens_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            sku="test",
            title=long_title,
            price=10.0,
            image_url="",
            url="",
        )

        assert len(hit["title"]) == 500

    def test_normalize_listing_custom_condition(self):
        from app.agents.adapters.gouletpens_caller import _normalize_listing

        hit = _normalize_listing(
            sku="test",
            title="Test Pen",
            price=50.0,
            image_url="",
            url="",
            condition="Used",
        )
        assert hit["condition"] == "Used"


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.gouletpens_caller import SUPPORTED_CATEGORIES

        assert "pens" in SUPPORTED_CATEGORIES


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestGouletPensCircuitBreaker:

    def test_gouletpens_circuit_exists(self):
        from workers.circuit_breaker import gouletpens_circuit
        assert gouletpens_circuit.name == "gouletpens"
        assert gouletpens_circuit.max_failures == 5
        assert gouletpens_circuit.cooldown_seconds == 60

    def test_gouletpens_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "gouletpens" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestGouletPensRegionConfig:

    def test_gouletpens_enabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "gouletpens") is True

    def test_gouletpens_disabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "gouletpens") is False

    def test_gouletpens_disabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "gouletpens") is False

    def test_gouletpens_disabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "gouletpens") is False

    def test_gouletpens_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "gouletpens") is True


# ---------------------------------------------------------------------------
# Source reliability
# ---------------------------------------------------------------------------


class TestGouletPensReliability:

    def test_gouletpens_reliability_constant(self):
        from app.agents.adapters.gouletpens_caller import GOULETPENS_SOURCE_RELIABILITY
        assert GOULETPENS_SOURCE_RELIABILITY == 0.80

    def test_gouletpens_in_marketplace_agent_reliability(self):
        from app.agents.marketplace_agent import SOURCE_RELIABILITY
        assert "gouletpens" in SOURCE_RELIABILITY
        assert SOURCE_RELIABILITY["gouletpens"] == 0.80
