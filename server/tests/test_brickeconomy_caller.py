"""Tests for the BrickEconomy marketplace caller.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - search() returns empty on circuit open
  - search() HTML parsing / normalisation
  - search() non-200 records failure
  - search() network exception records failure
  - sold_comps() returns historical price data
  - sold_comps() returns empty when not configured
  - sold_comps() returns empty on circuit open
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

from workers.circuit_breaker import brickeconomy_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    brickeconomy_circuit.reset()
    yield
    brickeconomy_circuit.reset()


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

SAMPLE_BRICKECONOMY_SEARCH_HTML = """
<html>
<body>
<div class="set-card">
  <a href="/set/75192-1/millennium-falcon">
    <div class="ctitle">LEGO 75192 Millennium Falcon</div>
    <img src="https://www.brickeconomy.com/img/sets/75192.jpg" />
    <span class="price">$849.99</span>
    <span class="price">$799.99</span>
    <span class="growth">+12.5%</span>
  </a>
</div>
<div class="set-card">
  <a href="/set/10294-1/titanic">
    <div class="ctitle">LEGO 10294 Titanic</div>
    <img src="https://www.brickeconomy.com/img/sets/10294.jpg" />
    <span class="price">$679.99</span>
    <span class="price">$629.99</span>
    <span class="growth">+8.3%</span>
  </a>
</div>
</body>
</html>
"""

SAMPLE_BRICKECONOMY_DETAIL_HTML = """
<html>
<body>
<h1>LEGO 75192 Millennium Falcon</h1>
<div class="price-history">
  <div>Jan 2024 $750.00</div>
  <div>Jul 2024 $800.00</div>
  <div>Jan 2025 $849.99</div>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestBrickEconomyCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestBrickEconomyCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller
        return BrickEconomyCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        for _ in range(10):
            brickeconomy_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_BRICKECONOMY_SEARCH_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("millennium falcon")

        assert len(results) >= 1
        hit = results[0]
        assert hit["source"] == "brickeconomy"
        assert hit["raw_id"].startswith("brickecon-")
        assert hit["currency"] == "USD"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "brickeconomy.com" in hit["url"]

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.brickeconomy_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.brickeconomy_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.brickeconomy_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestBrickEconomyCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_not_configured(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_on_circuit_open(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        for _ in range(10):
            brickeconomy_circuit.record_failure()

        caller = BrickEconomyCaller(enabled=True)
        result = await caller.sold_comps("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_parses_price_history(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        # Search page returns a set link
        search_html = '<html><a href="/set/75192-1/millennium-falcon">Set</a></html>'
        # Detail page has price history
        detail_html = SAMPLE_BRICKECONOMY_DETAIL_HTML

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _fake_response(200, text=search_html)
            else:
                return _fake_response(200, text=detail_html)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = mock_get
        mock_client.is_closed = False

        caller = BrickEconomyCaller(enabled=True)
        caller._http = mock_client

        results = await caller.sold_comps("millennium falcon")

        assert len(results) >= 1
        for hit in results:
            assert hit["source"] == "brickeconomy"
            assert hit["raw_id"].startswith("brickecon-")
            assert hit["is_sold"] is True
            assert hit["sold_at"] is not None
            assert hit["price"] > 0

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_no_set_match(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html>No results</html>"))
        mock_client.is_closed = False

        caller = BrickEconomyCaller(enabled=True)
        caller._http = mock_client

        results = await caller.sold_comps("nonexistent set")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_network_error(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False

        caller = BrickEconomyCaller(enabled=True)
        caller._http = mock_client

        results = await caller.sold_comps("test")
        assert results == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestBrickEconomyCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestBrickEconomyCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller

        caller = BrickEconomyCaller(enabled=True)
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_parse_price_dollar_sign(self):
        from app.agents.adapters.brickeconomy_caller import _parse_price

        assert _parse_price("$849.99") == 849.99

    def test_parse_price_no_symbol(self):
        from app.agents.adapters.brickeconomy_caller import _parse_price

        assert _parse_price("679.99") == 679.99

    def test_parse_price_with_commas(self):
        from app.agents.adapters.brickeconomy_caller import _parse_price

        assert _parse_price("$1,299.99") == 1299.99

    def test_parse_price_empty(self):
        from app.agents.adapters.brickeconomy_caller import _parse_price

        assert _parse_price("") == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.brickeconomy_caller import _normalize_listing

        hit = _normalize_listing(
            set_number="75192",
            title="LEGO 75192 Millennium Falcon",
            price=849.99,
            image_url="https://www.brickeconomy.com/img/75192.jpg",
            url="https://www.brickeconomy.com/set/75192-1/millennium-falcon",
        )

        assert hit["source"] == "brickeconomy"
        assert hit["raw_id"] == "brickecon-75192"
        assert hit["title"] == "LEGO 75192 Millennium Falcon"
        assert hit["price"] == 849.99
        assert hit["currency"] == "USD"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "brickeconomy.com" in hit["url"]

    def test_normalize_listing_with_retail_and_growth(self):
        from app.agents.adapters.brickeconomy_caller import _normalize_listing

        hit = _normalize_listing(
            set_number="75192",
            title="LEGO 75192 Millennium Falcon",
            price=849.99,
            image_url="",
            url="https://www.brickeconomy.com/set/75192-1/millennium-falcon",
            retail_price=799.99,
            growth_pct=12.5,
        )

        assert hit["retail_price"] == 799.99
        assert hit["annual_growth_pct"] == 12.5

    def test_normalize_listing_sold(self):
        from app.agents.adapters.brickeconomy_caller import _normalize_listing

        hit = _normalize_listing(
            set_number="75192",
            title="LEGO 75192",
            price=750.00,
            image_url="",
            url="",
            is_sold=True,
            sold_at="2024-01-01",
        )

        assert hit["is_sold"] is True
        assert hit["sold_at"] == "2024-01-01"

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.brickeconomy_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            set_number="12345",
            title=long_title,
            price=10.0,
            image_url="",
            url="",
        )

        assert len(hit["title"]) == 500


# ---------------------------------------------------------------------------
# Supported categories constant
# ---------------------------------------------------------------------------


class TestSupportedCategories:

    def test_supported_categories_contains_expected(self):
        from app.agents.adapters.brickeconomy_caller import SUPPORTED_CATEGORIES

        assert "lego" in SUPPORTED_CATEGORIES


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestBrickEconomyCircuitBreaker:

    def test_brickeconomy_circuit_exists(self):
        from workers.circuit_breaker import brickeconomy_circuit
        assert brickeconomy_circuit.name == "brickeconomy"
        assert brickeconomy_circuit.max_failures == 5
        assert brickeconomy_circuit.cooldown_seconds == 60

    def test_brickeconomy_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "brickeconomy" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestBrickEconomyRegionConfig:

    def test_brickeconomy_enabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "brickeconomy") is True

    def test_brickeconomy_enabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "brickeconomy") is True

    def test_brickeconomy_enabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "brickeconomy") is True

    def test_brickeconomy_enabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "brickeconomy") is True

    def test_brickeconomy_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "brickeconomy") is True


# ---------------------------------------------------------------------------
# Source reliability
# ---------------------------------------------------------------------------


class TestBrickEconomyReliability:

    def test_brickeconomy_reliability_constant(self):
        from app.agents.adapters.brickeconomy_caller import BRICKECONOMY_SOURCE_RELIABILITY
        assert BRICKECONOMY_SOURCE_RELIABILITY == 0.85

    def test_brickeconomy_sold_reliability_constant(self):
        from app.agents.adapters.brickeconomy_caller import BRICKECONOMY_SOLD_RELIABILITY
        assert BRICKECONOMY_SOLD_RELIABILITY == 0.90

    def test_brickeconomy_in_marketplace_agent_reliability(self):
        from app.agents.marketplace_agent import SOURCE_RELIABILITY
        assert "brickeconomy" in SOURCE_RELIABILITY
        assert SOURCE_RELIABILITY["brickeconomy"] == 0.85
        assert "brickeconomy_sold" in SOURCE_RELIABILITY
        assert SOURCE_RELIABILITY["brickeconomy_sold"] == 0.90
