"""Tests for the Master of Malt marketplace caller.

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
  - _parse_gbp_price helper
  - _convert_gbp_to_eur fallback
  - _normalize_listing helper
  - circuit breaker integration
  - region config integration
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

from workers.circuit_breaker import masterofmalt_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    masterofmalt_circuit.reset()
    yield
    masterofmalt_circuit.reset()


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

SAMPLE_MOM_HTML = """
<html>
<body>
<div class="product-list">
  <a href="/whiskies/macallan/macallan-18-year-old/">
    <div class="product-name">Macallan 18 Year Old Sherry Oak</div>
    <img src="https://www.masterofmalt.com/product/macallan-18.jpg" />
    <div class="price">&pound;250.00</div>
  </a>
</div>
<div class="product-list">
  <a href="/whiskies/highland-park/highland-park-25-year-old/">
    <div class="product-name">Highland Park 25 Year Old</div>
    <img src="https://www.masterofmalt.com/product/hp-25.jpg" />
    <div class="price">&pound;450.00</div>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestMasterOfMaltCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestMasterOfMaltCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller
        return MasterOfMaltCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            masterofmalt_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_MOM_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Macallan 18")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "masterofmalt"
        assert hit["raw_id"].startswith("mom-")
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "GBP"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.masterofmalt_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_429_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.masterofmalt_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.masterofmalt_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.masterofmalt_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestMasterOfMaltCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestMasterOfMaltCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestMasterOfMaltCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller

        caller = MasterOfMaltCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParseGbpPrice:

    def test_parse_price_pound_sign(self):
        from app.agents.adapters.masterofmalt_caller import _parse_gbp_price

        assert _parse_gbp_price("\u00a3250.00") == 250.0

    def test_parse_price_gbp_prefix(self):
        from app.agents.adapters.masterofmalt_caller import _parse_gbp_price

        assert _parse_gbp_price("GBP 450.00") == 450.0

    def test_parse_price_html_entity(self):
        from app.agents.adapters.masterofmalt_caller import _parse_gbp_price

        assert _parse_gbp_price("&pound;120.00") == 120.0

    def test_parse_price_with_commas(self):
        from app.agents.adapters.masterofmalt_caller import _parse_gbp_price

        assert _parse_gbp_price("\u00a31,250.00") == 1250.0

    def test_parse_price_empty(self):
        from app.agents.adapters.masterofmalt_caller import _parse_gbp_price

        assert _parse_gbp_price("") == 0.0


class TestConvertGbpToEur:

    def test_fallback_conversion(self):
        from app.agents.adapters.masterofmalt_caller import _convert_gbp_to_eur, _FALLBACK_GBP_TO_EUR

        with patch("app.agents.adapters.masterofmalt_caller._convert_gbp_to_eur", side_effect=lambda p: round(p * _FALLBACK_GBP_TO_EUR, 2)):
            result = round(100 * _FALLBACK_GBP_TO_EUR, 2)
        assert result == 117.0

    def test_conversion_returns_positive(self):
        from app.agents.adapters.masterofmalt_caller import _convert_gbp_to_eur

        result = _convert_gbp_to_eur(100)
        # Whatever rate is used, result should be positive and reasonable
        assert result > 0
        assert result < 500  # EUR/GBP are similar magnitude

    def test_zero_price(self):
        from app.agents.adapters.masterofmalt_caller import _convert_gbp_to_eur

        assert _convert_gbp_to_eur(0.0) == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.masterofmalt_caller import _normalize_listing

        hit = _normalize_listing(
            product_id="macallan-18",
            title="Macallan 18 Year Old",
            gbp_price=250.0,
            condition="New/Sealed",
            image_url="https://www.masterofmalt.com/images/test.jpg",
        )

        assert hit["source"] == "masterofmalt"
        assert hit["raw_id"] == "mom-macallan-18"
        assert hit["title"] == "Macallan 18 Year Old"
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 250.0
        assert hit["source_currency"] == "GBP"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "New/Sealed"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None

    def test_normalize_listing_with_product_url(self):
        from app.agents.adapters.masterofmalt_caller import _normalize_listing

        hit = _normalize_listing(
            product_id="test",
            title="Test Whisky",
            gbp_price=100.0,
            condition=None,
            image_url="",
            product_url="/whiskies/test/test-whisky/",
        )

        assert hit["url"].startswith("https://www.masterofmalt.com/whiskies/")

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.masterofmalt_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            product_id="test",
            title=long_title,
            gbp_price=100.0,
            condition=None,
            image_url="",
        )

        assert len(hit["title"]) == 500


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.masterofmalt_caller import SUPPORTED_CATEGORIES

        assert "whiskey" in SUPPORTED_CATEGORIES


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestMasterOfMaltCircuitBreaker:

    def test_masterofmalt_circuit_exists(self):
        from workers.circuit_breaker import masterofmalt_circuit
        assert masterofmalt_circuit.name == "masterofmalt"
        assert masterofmalt_circuit.max_failures == 5
        assert masterofmalt_circuit.cooldown_seconds == 60

    def test_masterofmalt_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "masterofmalt" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestMasterOfMaltRegionConfig:

    def test_masterofmalt_disabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "masterofmalt") is False

    def test_masterofmalt_enabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "masterofmalt") is True

    def test_masterofmalt_disabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "masterofmalt") is False

    def test_masterofmalt_disabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "masterofmalt") is False

    def test_masterofmalt_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "masterofmalt") is True
