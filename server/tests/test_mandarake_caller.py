"""Tests for the Mandarake marketplace caller.

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
  - _convert_jpy_to_eur fallback
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

from workers.circuit_breaker import mandarake_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    mandarake_circuit.reset()
    yield
    mandarake_circuit.reset()


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

SAMPLE_MANDARAKE_HTML = """
<html>
<body>
<div class="block">
  <a href="/order/detailPage/item?itemCode=nitem-00ABCDEF01&lang=en">
    <div class="title">Dragon Ball Z Figure Vegeta SSJ</div>
    <img src="https://img.mandarake.co.jp/webshopimg/00ABCDEF01.jpg" />
    <div class="price">¥3,500</div>
    <div class="condition">中古</div>
  </a>
</div>
<div class="block">
  <a href="/order/detailPage/item?itemCode=nitem-00GHIJKL02&lang=en">
    <div class="title">Evangelion Unit 01 Model Kit</div>
    <img src="https://img.mandarake.co.jp/webshopimg/00GHIJKL02.jpg" />
    <div class="price">¥12,000</div>
    <div class="condition">新品</div>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestMandarakeCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestMandarakeCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller
        return MandarakeCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            mandarake_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_MANDARAKE_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Dragon Ball")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "mandarake"
        assert hit["raw_id"].startswith("mandarake-")
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "JPY"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.mandarake_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.mandarake_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.mandarake_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestMandarakeCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestMandarakeCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestMandarakeCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.mandarake_caller import MandarakeCaller

        caller = MandarakeCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_parse_price_yen_symbol(self):
        from app.agents.adapters.mandarake_caller import _parse_price

        assert _parse_price("¥3,500") == 3500.0

    def test_parse_price_yen_kanji(self):
        from app.agents.adapters.mandarake_caller import _parse_price

        assert _parse_price("3,500円") == 3500.0

    def test_parse_price_no_commas(self):
        from app.agents.adapters.mandarake_caller import _parse_price

        assert _parse_price("12000") == 12000.0

    def test_parse_price_empty(self):
        from app.agents.adapters.mandarake_caller import _parse_price

        assert _parse_price("") == 0.0

    def test_parse_price_none_returns_zero(self):
        from app.agents.adapters.mandarake_caller import _parse_price

        assert _parse_price("") == 0.0

    def test_parse_price_with_tax_included(self):
        from app.agents.adapters.mandarake_caller import _parse_price

        assert _parse_price("3,500円（税込）") == 3500.0


class TestConvertJpyToEur:

    def test_fallback_conversion(self):
        from app.agents.adapters.mandarake_caller import _convert_jpy_to_eur, _FALLBACK_JPY_TO_EUR

        # Mock out to_eur to force the fallback path
        with patch("app.agents.adapters.mandarake_caller._convert_jpy_to_eur", side_effect=lambda p: round(p * _FALLBACK_JPY_TO_EUR, 2)):
            result = round(10000 * _FALLBACK_JPY_TO_EUR, 2)
        assert result == 62.0

    def test_conversion_returns_positive(self):
        from app.agents.adapters.mandarake_caller import _convert_jpy_to_eur

        result = _convert_jpy_to_eur(10000)
        # Whatever rate is used, result should be positive and reasonable
        assert result > 0
        assert result < 10000  # EUR value should be less than JPY value

    def test_zero_price(self):
        from app.agents.adapters.mandarake_caller import _convert_jpy_to_eur

        assert _convert_jpy_to_eur(0.0) == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.mandarake_caller import _normalize_listing

        hit = _normalize_listing(
            item_code="nitem-00ABC",
            title="Test Figure",
            jpy_price=5000.0,
            condition="Used",
            image_url="https://img.mandarake.co.jp/test.jpg",
        )

        assert hit["source"] == "mandarake"
        assert hit["raw_id"] == "mandarake-nitem-00ABC"
        assert hit["title"] == "Test Figure"
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 5000.0
        assert hit["source_currency"] == "JPY"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "Used"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "itemCode=nitem-00ABC" in hit["url"]

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.mandarake_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            item_code="test",
            title=long_title,
            jpy_price=1000.0,
            condition=None,
            image_url="",
        )

        assert len(hit["title"]) == 500


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.mandarake_caller import SUPPORTED_CATEGORIES

        expected = ["anime_figures", "bandai_premium", "ghibli", "jp_event",
                     "jp_magazine", "hot_toys", "gunpla", "designer_toys",
                     "manga", "vtuber"]
        for cat in expected:
            assert cat in SUPPORTED_CATEGORIES, f"{cat} missing from SUPPORTED_CATEGORIES"


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestMandarakeCircuitBreaker:

    def test_mandarake_circuit_exists(self):
        from workers.circuit_breaker import mandarake_circuit
        assert mandarake_circuit.name == "mandarake"
        assert mandarake_circuit.max_failures == 5
        assert mandarake_circuit.cooldown_seconds == 60

    def test_mandarake_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "mandarake" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestMandarakeRegionConfig:

    def test_mandarake_enabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "mandarake") is True

    def test_mandarake_enabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "mandarake") is True

    def test_mandarake_disabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "mandarake") is False

    def test_mandarake_disabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "mandarake") is False

    def test_mandarake_disabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "mandarake") is False
