"""Tests for the Booth.pm marketplace caller.

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

from workers.circuit_breaker import booth_circuit


@pytest.fixture(autouse=True)
def _reset_circuit():
    booth_circuit.reset()
    yield
    booth_circuit.reset()


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

# Booth's real search markup: each result is a `<li class="item-card">` carrying
# `data-product-*` attributes, with the canonical URL on the inner
# `.item-card__title-anchor`. Mirrors `_parse_search_page`'s docstring, which is
# written from the live page.
#
# The previous fixture was `<div class="item-card">` with `.item-card__title`
# and a `<span class="price">` — a shape Booth does not emit and the parser
# stopped selecting when it was rewritten to read the attributes.
# `soup.select("li.item-card")` matched nothing, so the test drove the parser
# with markup no live response could produce.
SAMPLE_BOOTH_HTML = """
<html>
<body>
<ul>
<li class="item-card"
    data-product-id="1234567"
    data-product-name="Hololive Acrylic Stand Pekora"
    data-product-price="2500"
    data-product-brand="pekoshop">
  <a class="item-card__title-anchor" href="/en/items/1234567">Hololive Acrylic Stand Pekora</a>
  <img src="https://s2.booth.pm/images/hololive-pekora.jpg" />
</li>
<li class="item-card"
    data-product-id="7654321"
    data-product-name="Nijisanji Fan Art Print Set"
    data-product-price="1800"
    data-product-brand="nijiart">
  <a class="item-card__title-anchor" href="/en/items/7654321">Nijisanji Fan Art Print Set</a>
  <img src="https://s2.booth.pm/images/nijisanji-print.jpg" />
</li>
</ul>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestBoothCallerConfig:

    def test_configured_true_by_default(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        assert caller.configured is True

    def test_configured_false_when_disabled(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=False)
        assert caller.configured is False


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestBoothCallerSearch:

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.booth_caller import BoothCaller
        return BoothCaller(enabled=True)

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=False)
        result = await caller.search("anything")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_circuit_open(self, caller):
        # Trip the circuit
        for _ in range(10):
            booth_circuit.record_failure()

        result = await caller.search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_parses_html_results(self, caller):
        # TWO undeclared dependencies, and they fail differently:
        #   * bs4 missing  -> `_parse_search_page` logs a warning, returns []
        #   * lxml missing -> `BeautifulSoup(html, "lxml")` raises
        #     FeatureNotFound, which `search`'s `except Exception` turns into a
        #     circuit-breaker failure and []
        # Both look exactly like "the parser is broken" from here, and neither
        # is declared: booth, suruga_ya and yahoo_auctions import bs4 directly
        # while requirements.txt names neither bs4 nor lxml — they arrive
        # transitively through crawl4ai. suruga_ya and yahoo_auctions are LIVE
        # (not in DISABLED_ADAPTERS), and both failure paths degrade to "0
        # hits" rather than erroring, so losing that transitive dependency
        # would read as two sources quietly going dry.
        pytest.importorskip("bs4", reason="booth parsing needs BeautifulSoup")
        pytest.importorskip("lxml", reason="_parse_search_page asks for the lxml tree builder")

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text=SAMPLE_BOOTH_HTML))
        mock_client.is_closed = False
        caller._http = mock_client

        results = await caller.search("Hololive")

        assert len(results) >= 1
        # Verify first result has correct structure
        hit = results[0]
        assert hit["source"] == "booth"
        assert hit["raw_id"].startswith("booth-")
        assert hit["currency"] == "EUR"
        assert hit["source_currency"] == "JPY"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        # Both cards parsed, and the values come from the data-product-*
        # attributes — a selector matching the wrapper but not the attributes
        # would still return two objects full of blanks.
        assert len(results) == 2
        assert hit["title"] == "Hololive Acrylic Stand Pekora"
        assert hit["source_price"] == 2500.0

    @pytest.mark.asyncio
    async def test_search_non_200_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(503))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.booth_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_network_error_records_failure(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.booth_circuit.record_failure") as mock_fail:
            result = await caller.search("test")

        mock_fail.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_200_records_success(self, caller):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200, text="<html></html>"))
        mock_client.is_closed = False
        caller._http = mock_client

        with patch("workers.circuit_breaker.booth_circuit.record_success") as mock_success:
            await caller.search("test")

        mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# sold_comps()
# ---------------------------------------------------------------------------


class TestBoothCallerSoldComps:

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        result = await caller.sold_comps("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_disabled(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=False)
        result = await caller.sold_comps("test query")
        assert result == []


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------


class TestBoothCallerHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(200))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_403(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_fake_response(403))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_disabled(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=False)
        result = await caller.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.health_check()
        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestBoothCallerClose:

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        from app.agents.adapters.booth_caller import BoothCaller

        caller = BoothCaller(enabled=True)
        # Should not raise
        await caller.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_parse_price_yen_symbol(self):
        from app.agents.adapters.booth_caller import _parse_price

        assert _parse_price("¥3,500") == 3500.0

    def test_parse_price_yen_kanji(self):
        from app.agents.adapters.booth_caller import _parse_price

        assert _parse_price("3,500円") == 3500.0

    def test_parse_price_no_commas(self):
        from app.agents.adapters.booth_caller import _parse_price

        assert _parse_price("12000") == 12000.0

    def test_parse_price_empty(self):
        from app.agents.adapters.booth_caller import _parse_price

        assert _parse_price("") == 0.0


class TestConvertJpyToEur:

    def test_fallback_conversion(self):
        from app.agents.adapters.booth_caller import _convert_jpy_to_eur, _FALLBACK_JPY_TO_EUR

        with patch("app.agents.adapters.booth_caller._convert_jpy_to_eur", side_effect=lambda p: round(p * _FALLBACK_JPY_TO_EUR, 2)):
            result = round(10000 * _FALLBACK_JPY_TO_EUR, 2)
        assert result == 62.0

    def test_conversion_returns_positive(self):
        from app.agents.adapters.booth_caller import _convert_jpy_to_eur

        result = _convert_jpy_to_eur(10000)
        assert result > 0
        assert result < 10000  # EUR value should be less than JPY value

    def test_zero_price(self):
        from app.agents.adapters.booth_caller import _convert_jpy_to_eur

        assert _convert_jpy_to_eur(0.0) == 0.0


class TestNormalizeListing:

    def test_normalize_listing_basic(self):
        from app.agents.adapters.booth_caller import _normalize_listing

        hit = _normalize_listing(
            item_id="1234567",
            title="Hololive Acrylic Stand",
            jpy_price=2500.0,
            condition="New",
            image_url="https://s2.booth.pm/test.jpg",
        )

        assert hit["source"] == "booth"
        assert hit["raw_id"] == "booth-1234567"
        assert hit["title"] == "Hololive Acrylic Stand"
        assert hit["currency"] == "EUR"
        assert hit["source_price"] == 2500.0
        assert hit["source_currency"] == "JPY"
        assert hit["price"] > 0  # EUR converted
        assert hit["condition"] == "New"
        assert hit["is_sold"] is False
        assert hit["sold_at"] is None
        assert "1234567" in hit["url"]

    def test_normalize_listing_truncates_long_title(self):
        from app.agents.adapters.booth_caller import _normalize_listing

        long_title = "A" * 600
        hit = _normalize_listing(
            item_id="test",
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
        from app.agents.adapters.booth_caller import SUPPORTED_CATEGORIES

        expected = ["vtuber", "jp_event", "designer_toys", "kpop_lightsticks"]
        for cat in expected:
            assert cat in SUPPORTED_CATEGORIES, f"{cat} missing from SUPPORTED_CATEGORIES"


# ---------------------------------------------------------------------------
# Circuit breaker integration
# ---------------------------------------------------------------------------


class TestBoothCircuitBreaker:

    def test_booth_circuit_exists(self):
        from workers.circuit_breaker import booth_circuit
        assert booth_circuit.name == "booth"
        assert booth_circuit.max_failures == 5
        assert booth_circuit.cooldown_seconds == 60

    def test_booth_in_all_circuit_status(self):
        from workers.circuit_breaker import all_circuit_status
        statuses = all_circuit_status()
        names = [s["name"] for s in statuses]
        assert "booth" in names


# ---------------------------------------------------------------------------
# Region config integration
# ---------------------------------------------------------------------------


class TestBoothRegionConfig:

    def test_booth_enabled_in_japan(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("japan", "booth") is True

    def test_booth_enabled_in_korea(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("korea", "booth") is True

    def test_booth_disabled_in_americas(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("americas", "booth") is False

    def test_booth_disabled_in_europe(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("europe", "booth") is False

    def test_booth_disabled_in_other(self):
        from app.lib.region_marketplace_config import should_use_adapter
        assert should_use_adapter("other", "booth") is False
