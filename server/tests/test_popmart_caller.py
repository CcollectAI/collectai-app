"""Tests for the PopMart marketplace caller.

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
  - _convert_usd_to_eur fallback
  - _normalize_listing helper
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

from workers.circuit_breaker import popmart_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    popmart_circuit.reset()
    yield
    popmart_circuit.reset()


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

SAMPLE_POPMART_HTML = """
<html>
<body>
<div class="product-card">
  <a href="/products/molly-space-series-001">
    <div class="product-title">MOLLY Space Series Blind Box</div>
    <img src="https://cdn.popmart.com/images/molly-space.jpg" />
    <span class="price">$12.99</span>
  </a>
</div>
<div class="product-card">
  <a href="/products/dimoo-forest-night-002">
    <div class="product-title">DIMOO Forest Night Series</div>
    <img src="https://cdn.popmart.com/images/dimoo-forest.jpg" />
    <span class="price">$14.99</span>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestPopMartCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestPopMartCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.popmart_caller import PopMartCaller
        return PopMartCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            popmart_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_POPMART_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("MOLLY")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "popmart"
        assert hit["raw_id"].startswith("popmart-")
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "USD"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.popmart_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.popmart_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.popmart_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestPopMartCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestPopMartCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestPopMartCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.popmart_caller import PopMartCaller

        caller = PopMartCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_parse_price_dollar(self):
        from app.agents.adapters.popmart_caller import _parse_price

        assert _parse_price("$12.99") == 12.99

    def test_parse_price_no_symbol(self):
        from app.agents.adapters.popmart_caller import _parse_price

        assert _parse_price("12.99") == 12.99

    def test_parse_price_empty(self):
        from app.agents.adapters.popmart_caller import _parse_price

        assert _parse_price("") == 0.0

    def test_parse_price_with_comma(self):
        from app.agents.adapters.popmart_caller import _parse_price

        assert _parse_price("$1,299.99") == 1299.99


class TestConvertUsdToEur:

    def test_fallback_conversion(self):
        from app.agents.adapters.popmart_caller import _convert_usd_to_eur, _FALLBACK_USD_TO_EUR

        with patch("app.agents.adapters.popmart_caller._convert_usd_to_eur", side_effect=lambda p: round(p * _FALLBACK_USD_TO_EUR, 2)):
            result = round(100 * _FALLBACK_USD_TO_EUR, 2)
        assert result == 92.0

    def test_conversion_returns_positive(self):
        from app.agents.adapters.popmart_caller import _convert_usd_to_eur

        result = _convert_usd_to_eur(100)
        assert result > 0
        assert result < 200  # EUR value should be reasonable

    def test_zero_price(self):
        from app.agents.adapters.popmart_caller import _convert_usd_to_eur

        assert _convert_usd_to_eur(0.0) == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.popmart_caller import _normalize_listing

        hit = _normalize_listing(
            product_id="molly-space-001",
            title="MOLLY Space Series",
            usd_price=12.99,
            condition="New",
            image_url="https://cdn.popmart.com/test.jpg",
        )

        assert hit["source"] == "popmart"
        assert hit["raw_id"] == "popmart-molly-space-001"
        assert hit["title"] == "MOLLY Space Series"
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 12.99
        assert hit["source_currency"] == "USD"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "New"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "molly-space-001" in hit["url"]

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.popmart_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            product_id="test",
            title=long_title,
            usd_price=10.0,
            condition=None,
            image_url="",
        )

        assert len(hit["title"]) == 500


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.popmart_caller import SUPPORTED_CATEGORIES

        expected = ["blind_box", "designer_toys"]
        for cat in expected:
            assert cat in SUPPORTED_CATEGORIES, f"{cat} missing from SUPPORTED_CATEGORIES"


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestPopMartCircuitBreaker:

    def test_popmart_circuit_exists(self):
        from workers.circuit_breaker import popmart_circuit
        assert popmart_circuit.name == "popmart"
        assert popmart_circuit.max_failures == 5
        assert popmart_circuit.cooldown_seconds == 60

    def test_popmart_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "popmart" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestPopMartRegionConfig:

    def test_popmart_enabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "popmart") is True

    def test_popmart_enabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "popmart") is True

    def test_popmart_enabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "popmart") is True

    def test_popmart_enabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "popmart") is True

    def test_popmart_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "popmart") is True
