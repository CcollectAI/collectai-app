"""Tests for the ScaleMates marketplace caller.

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
  - _convert_to_eur helper
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

from workers.circuit_breaker import scalemates_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    scalemates_circuit.reset()
    yield
    scalemates_circuit.reset()


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

SAMPLE_SCALEMATES_HTML = """
<html>
<body>
<div class="search-result">
  <a href="/kits/tamiya-spitfire--12345">
    <div class="product-name">Spitfire Mk.V</div>
    <div class="manufacturer">Tamiya</div>
    <span class="scale">1:48</span>
    <img src="https://s.scalemates.com/images/spitfire.jpg" />
    <span class="price">$24.99</span>
  </a>
</div>
<div class="search-result">
  <a href="/kits/bandai-rx-78-2--67890">
    <div class="product-name">RX-78-2 Gundam</div>
    <div class="manufacturer">Bandai</div>
    <span class="scale">1:144</span>
    <img src="https://s.scalemates.com/images/gundam.jpg" />
    <span class="price">€18.50</span>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestScaleMatesCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestScaleMatesCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller
        return ScaleMatesCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            scalemates_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_SCALEMATES_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Spitfire")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "scalemates"
        assert hit["raw_id"].startswith("scalemates-")
        assert hit["currency"] == "EUR"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.scalemates_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.scalemates_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.scalemates_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestScaleMatesCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestScaleMatesCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestScaleMatesCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.scalemates_caller import ScaleMatesCaller

        caller = ScaleMatesCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_parse_price_usd(self):
        from app.agents.adapters.scalemates_caller import _parse_price

        price, currency = _parse_price("$24.99")
        assert price == 24.99
        assert currency == "USD"

    def test_parse_price_eur(self):
        from app.agents.adapters.scalemates_caller import _parse_price

        price, currency = _parse_price("€18.50")
        assert price == 18.50
        assert currency == "EUR"

    def test_parse_price_gbp(self):
        from app.agents.adapters.scalemates_caller import _parse_price

        price, currency = _parse_price("£15.99")
        assert price == 15.99
        assert currency == "GBP"

    def test_parse_price_empty(self):
        from app.agents.adapters.scalemates_caller import _parse_price

        price, currency = _parse_price("")
        assert price == 0.0
        assert currency == "EUR"


class TestConvertToEur:

    def test_eur_passthrough(self):
        from app.agents.adapters.scalemates_caller import _convert_to_eur

        assert _convert_to_eur(25.0, "EUR") == 25.0

    def test_usd_conversion_returns_positive(self):
        from app.agents.adapters.scalemates_caller import _convert_to_eur

        result = _convert_to_eur(100.0, "USD")
        assert result > 0
        assert result < 200

    def test_zero_price(self):
        from app.agents.adapters.scalemates_caller import _convert_to_eur

        assert _convert_to_eur(0.0, "USD") == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.scalemates_caller import _normalize_listing

        hit = _normalize_listing(
            kit_id="tamiya-spitfire--12345",
            title="Spitfire Mk.V",
            price=24.99,
            source_currency="USD",
            condition="New",
            image_url="https://s.scalemates.com/test.jpg",
            scale="1:48",
            manufacturer="Tamiya",
        )

        assert hit["source"] == "scalemates"
        assert hit["raw_id"] == "scalemates-tamiya-spitfire--12345"
        assert "[1:48]" in hit["title"]
        assert "(Tamiya)" in hit["title"]
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 24.99
        assert hit["source_currency"] == "USD"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "New"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "tamiya-spitfire--12345" in hit["url"]

    def test_normalize_listing_no_scale_no_manufacturer(self):
        from app.agents.adapters.scalemates_caller import _normalize_listing

        hit = _normalize_listing(
            kit_id="test",
            title="Test Kit",
            price=10.0,
            source_currency="EUR",
            condition=None,
            image_url="",
            scale=None,
            manufacturer=None,
        )

        assert hit["title"] == "Test Kit"
        assert "[" not in hit["title"]
        assert "(" not in hit["title"]

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.scalemates_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            kit_id="test",
            title=long_title,
            price=10.0,
            source_currency="EUR",
            condition=None,
            image_url="",
        )

        assert len(hit["title"]) == 500


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.scalemates_caller import SUPPORTED_CATEGORIES

        expected = ["scale_models", "gunpla", "diecast"]
        for cat in expected:
            assert cat in SUPPORTED_CATEGORIES, f"{cat} missing from SUPPORTED_CATEGORIES"


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestScaleMatesCircuitBreaker:

    def test_scalemates_circuit_exists(self):
        from workers.circuit_breaker import scalemates_circuit
        assert scalemates_circuit.name == "scalemates"
        assert scalemates_circuit.max_failures == 5
        assert scalemates_circuit.cooldown_seconds == 60

    def test_scalemates_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "scalemates" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestScaleMatesRegionConfig:

    def test_scalemates_enabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "scalemates") is True

    def test_scalemates_enabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "scalemates") is True

    def test_scalemates_enabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "scalemates") is True

    def test_scalemates_enabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "scalemates") is True

    def test_scalemates_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "scalemates") is True
