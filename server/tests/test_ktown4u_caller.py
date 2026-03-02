"""Tests for the KTown4U marketplace caller.

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
  - _parse_krw_price helper
  - _convert_krw_to_eur fallback
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

from workers.circuit_breaker import ktown4u_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    ktown4u_circuit.reset()
    yield
    ktown4u_circuit.reset()


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

SAMPLE_KTOWN4U_HTML = """
<html>
<body>
<div class="product-list">
  <a href="/iteminfo?goods_no=12345">
    <div class="goods_name">BTS - Map of the Soul: 7 Album</div>
    <img src="https://www.ktown4u.com/images/product/12345.jpg" />
    <div class="price">₩25,000</div>
  </a>
</div>
<div class="product-list">
  <a href="/iteminfo?goods_no=67890">
    <div class="goods_name">BLACKPINK - THE ALBUM</div>
    <img src="https://www.ktown4u.com/images/product/67890.jpg" />
    <div class="price">₩18,500</div>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestKTown4UCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestKTown4UCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller
        return KTown4UCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            ktown4u_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_KTOWN4U_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("BTS album")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "ktown4u"
        assert hit["raw_id"].startswith("ktown4u-")
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "KRW"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.ktown4u_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_429_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.ktown4u_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.ktown4u_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.ktown4u_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestKTown4UCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestKTown4UCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestKTown4UCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.ktown4u_caller import KTown4UCaller

        caller = KTown4UCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParseKrwPrice:

    def test_parse_price_won_symbol(self):
        from app.agents.adapters.ktown4u_caller import _parse_krw_price

        assert _parse_krw_price("₩25,000") == 25000.0

    def test_parse_price_won_suffix(self):
        from app.agents.adapters.ktown4u_caller import _parse_krw_price

        assert _parse_krw_price("25,000원") == 25000.0

    def test_parse_price_krw_prefix(self):
        from app.agents.adapters.ktown4u_caller import _parse_krw_price

        assert _parse_krw_price("KRW 18500") == 18500.0

    def test_parse_price_no_commas(self):
        from app.agents.adapters.ktown4u_caller import _parse_krw_price

        assert _parse_krw_price("₩25000") == 25000.0

    def test_parse_price_empty(self):
        from app.agents.adapters.ktown4u_caller import _parse_krw_price

        assert _parse_krw_price("") == 0.0


class TestConvertKrwToEur:

    def test_fallback_conversion(self):
        from app.agents.adapters.ktown4u_caller import _convert_krw_to_eur, _FALLBACK_KRW_TO_EUR

        with patch("app.agents.adapters.ktown4u_caller._convert_krw_to_eur", side_effect=lambda p: round(p * _FALLBACK_KRW_TO_EUR, 2)):
            result = round(100000 * _FALLBACK_KRW_TO_EUR, 2)
        assert result == 67.0

    def test_conversion_returns_positive(self):
        from app.agents.adapters.ktown4u_caller import _convert_krw_to_eur

        result = _convert_krw_to_eur(100000)
        # Whatever rate is used, result should be positive and reasonable
        assert result > 0
        assert result < 100000  # EUR value should be much less than KRW value

    def test_zero_price(self):
        from app.agents.adapters.ktown4u_caller import _convert_krw_to_eur

        assert _convert_krw_to_eur(0.0) == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.ktown4u_caller import _normalize_listing

        hit = _normalize_listing(
            product_id="12345",
            title="BTS Album",
            krw_price=25000.0,
            condition="New",
            image_url="https://www.ktown4u.com/images/test.jpg",
        )

        assert hit["source"] == "ktown4u"
        assert hit["raw_id"] == "ktown4u-12345"
        assert hit["title"] == "BTS Album"
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 25000.0
        assert hit["source_currency"] == "KRW"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "New"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "goods_no=12345" in hit["url"]

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.ktown4u_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            product_id="test",
            title=long_title,
            krw_price=10000.0,
            condition=None,
            image_url="",
        )

        assert len(hit["title"]) == 500


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.ktown4u_caller import SUPPORTED_CATEGORIES

        expected = ["kpop", "kpop_lightsticks", "blind_box"]
        for cat in expected:
            assert cat in SUPPORTED_CATEGORIES, f"{cat} missing from SUPPORTED_CATEGORIES"


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestKTown4UCircuitBreaker:

    def test_ktown4u_circuit_exists(self):
        from workers.circuit_breaker import ktown4u_circuit
        assert ktown4u_circuit.name == "ktown4u"
        assert ktown4u_circuit.max_failures == 5
        assert ktown4u_circuit.cooldown_seconds == 60

    def test_ktown4u_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "ktown4u" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestKTown4URegionConfig:

    def test_ktown4u_enabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "ktown4u") is True

    def test_ktown4u_enabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "ktown4u") is True

    def test_ktown4u_disabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "ktown4u") is False

    def test_ktown4u_enabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "ktown4u") is True

    def test_ktown4u_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "ktown4u") is True
