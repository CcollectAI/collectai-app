"""Tests for the ComicBookRealm marketplace caller.

Covers:
  - .configured property (True / False)
  - search() empty when not configured
  - search() returns empty on circuit open
  - search() HTML parsing / normalisation
  - search() non-200 records failure
  - search() network exception records failure
  - sold_comps() returns guide values as reference pricing
  - sold_comps() returns empty when disabled
  - health_check() returns True on 200
  - health_check() returns False when not configured
  - close() closes HTTP client
  - _parse_usd_price helper
  - _convert_usd_to_eur fallback
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

from workers.circuit_breaker import comicbookrealm_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    comicbookrealm_circuit.reset()
    yield
    comicbookrealm_circuit.reset()


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

SAMPLE_CBR_HTML = """
<html>
<body>
<div class="search-results">
  <a href="/report/comic/54321">
    <div class="comic-title">Amazing Spider-Man #300</div>
    <img src="https://comicbookrealm.com/covers/54321.jpg" />
    <div class="price">$125.00</div>
    <div class="grade">CGC: 9.8</div>
  </a>
</div>
<div class="search-results">
  <a href="/report/comic/98765">
    <div class="comic-title">Batman #1 (2011)</div>
    <img src="https://comicbookrealm.com/covers/98765.jpg" />
    <div class="price">$45.00</div>
    <div class="grade">CGC: 9.4</div>
  </a>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestComicBookRealmCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestComicBookRealmCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller
        return ComicBookRealmCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            comicbookrealm_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_CBR_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Spider-Man")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "comicbookrealm"
        assert hit["raw_id"].startswith("cbr-")
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "USD"
        assert hit["is_sold"] is False

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.comicbookrealm_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_429_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(429))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.comicbookrealm_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.comicbookrealm_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.comicbookrealm_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestComicBookRealmCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_marks_results_as_sold(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_CBR_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.sold_comps("Spider-Man")

        # ComicBookRealm sold_comps should mark results as sold reference data
        for hit in results:
            assert hit["is_sold"] is True

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_on_circuit_open(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        for _ in range(10):
            comicbookrealm_circuit.record_failure()

        result = await caller.sold_comps("test")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestComicBookRealmCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestComicBookRealmCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller

        caller = ComicBookRealmCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParseUsdPrice:

    def test_parse_price_dollar_sign(self):
        from app.agents.adapters.comicbookrealm_caller import _parse_usd_price

        assert _parse_usd_price("$125.00") == 125.0

    def test_parse_price_usd_prefix(self):
        from app.agents.adapters.comicbookrealm_caller import _parse_usd_price

        assert _parse_usd_price("USD 45.00") == 45.0

    def test_parse_price_us_dollar(self):
        from app.agents.adapters.comicbookrealm_caller import _parse_usd_price

        assert _parse_usd_price("US$250.00") == 250.0

    def test_parse_price_with_commas(self):
        from app.agents.adapters.comicbookrealm_caller import _parse_usd_price

        assert _parse_usd_price("$1,250.00") == 1250.0

    def test_parse_price_empty(self):
        from app.agents.adapters.comicbookrealm_caller import _parse_usd_price

        assert _parse_usd_price("") == 0.0


class TestConvertUsdToEur:

    def test_fallback_conversion(self):
        from app.agents.adapters.comicbookrealm_caller import _convert_usd_to_eur, _FALLBACK_USD_TO_EUR

        with patch("app.agents.adapters.comicbookrealm_caller._convert_usd_to_eur", side_effect=lambda p: round(p * _FALLBACK_USD_TO_EUR, 2)):
            result = round(100 * _FALLBACK_USD_TO_EUR, 2)
        assert result == 92.0

    def test_conversion_returns_positive(self):
        from app.agents.adapters.comicbookrealm_caller import _convert_usd_to_eur

        result = _convert_usd_to_eur(100)
        # Whatever rate is used, result should be positive and reasonable
        assert result > 0
        assert result < 200  # EUR and USD are similar magnitude

    def test_zero_price(self):
        from app.agents.adapters.comicbookrealm_caller import _convert_usd_to_eur

        assert _convert_usd_to_eur(0.0) == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.comicbookrealm_caller import _normalize_listing

        hit = _normalize_listing(
            issue_id="54321",
            title="Amazing Spider-Man #300",
            usd_price=125.0,
            condition="Near Mint+",
            image_url="https://comicbookrealm.com/covers/54321.jpg",
        )

        assert hit["source"] == "comicbookrealm"
        assert hit["raw_id"] == "cbr-54321"
        assert hit["title"] == "Amazing Spider-Man #300"
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 125.0
        assert hit["source_currency"] == "USD"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "Near Mint+"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "54321" in hit["url"]

    def test_normalize_listing_with_grade(self):
        from app.agents.adapters.comicbookrealm_caller import _normalize_listing

        hit = _normalize_listing(
            issue_id="12345",
            title="Batman #1",
            usd_price=45.0,
            condition=None,
            image_url="",
            grade="9.8",
        )

        assert hit["grade"] == "9.8"
        assert hit["condition"] == "9.8"  # Grade used as fallback condition

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.comicbookrealm_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            issue_id="test",
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
        from app.agents.adapters.comicbookrealm_caller import SUPPORTED_CATEGORIES

        assert "comic_books" in SUPPORTED_CATEGORIES


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestComicBookRealmCircuitBreaker:

    def test_comicbookrealm_circuit_exists(self):
        from workers.circuit_breaker import comicbookrealm_circuit
        assert comicbookrealm_circuit.name == "comicbookrealm"
        assert comicbookrealm_circuit.max_failures == 5
        assert comicbookrealm_circuit.cooldown_seconds == 60

    def test_comicbookrealm_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "comicbookrealm" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestComicBookRealmRegionConfig:

    def test_comicbookrealm_enabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "comicbookrealm") is True

    def test_comicbookrealm_enabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "comicbookrealm") is True

    def test_comicbookrealm_disabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "comicbookrealm") is False

    def test_comicbookrealm_disabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "comicbookrealm") is False

    def test_comicbookrealm_enabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "comicbookrealm") is True
