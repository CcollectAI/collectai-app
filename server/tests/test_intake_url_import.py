"""
Tests for URL import in intake_agent.py and intake_router.py.

Covers:
  - process_url_import() in intake_agent.py
  - POST /intake/url in intake_router.py
  - Helper functions: _detect_url_source, _convert_price_to_eur, _guess_category_from_url
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestDetectUrlSource:
    """Tests for _detect_url_source()."""

    def test_ebay_com(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://www.ebay.com/itm/123456") == "ebay"

    def test_ebay_co_uk(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://www.ebay.co.uk/itm/789") == "ebay"

    def test_mercari(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://www.mercari.com/item/abc") == "mercari"

    def test_mercari_jp(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://jp.mercari.com/item/abc") == "mercari_jp"

    def test_stockx(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://stockx.com/some-item") == "stockx"

    def test_tcgplayer(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://www.tcgplayer.com/product/12345") == "tcgplayer"

    def test_bricklink(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://www.bricklink.com/v2/catalog/catalogitem.page") == "bricklink"

    def test_mfc(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://myfigurecollection.net/item/12345") == "mfc"

    def test_ktown4u(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://www.ktown4u.com/item/123") == "ktown4u"

    def test_weverse(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://weverse.io/bts/shop/123") == "weverse"

    def test_unknown_site(self):
        from app.agents.intake_agent import _detect_url_source

        assert _detect_url_source("https://randomsite.com/item") is None


class TestConvertPriceToEur:
    """Tests for _convert_price_to_eur()."""

    def test_eur_passthrough(self):
        from app.agents.intake_agent import _convert_price_to_eur

        assert _convert_price_to_eur(10.0, "EUR") == 10.0

    def test_usd_conversion(self):
        from app.agents.intake_agent import _convert_price_to_eur

        result = _convert_price_to_eur(100.0, "USD")
        assert result == pytest.approx(92.0, abs=1.0)

    def test_jpy_conversion(self):
        from app.agents.intake_agent import _convert_price_to_eur

        result = _convert_price_to_eur(1000.0, "JPY")
        assert result == pytest.approx(6.1, abs=0.5)

    def test_gbp_conversion(self):
        from app.agents.intake_agent import _convert_price_to_eur

        result = _convert_price_to_eur(10.0, "GBP")
        assert result == pytest.approx(11.7, abs=0.5)

    def test_none_price(self):
        from app.agents.intake_agent import _convert_price_to_eur

        assert _convert_price_to_eur(None, "USD") is None

    def test_no_currency_is_eur(self):
        from app.agents.intake_agent import _convert_price_to_eur

        assert _convert_price_to_eur(25.0, None) == 25.0

    def test_unknown_currency_passthrough(self):
        from app.agents.intake_agent import _convert_price_to_eur

        assert _convert_price_to_eur(10.0, "XYZ") == 10.0


class TestGuessCategoryFromUrl:
    """Tests for _guess_category_from_url()."""

    def test_pokemon_url(self):
        from app.agents.intake_agent import _guess_category_from_url

        assert _guess_category_from_url(
            "https://ebay.com/itm/pokemon-card",
            {"title": "Charizard VMAX"},
        ) == "pokemon"

    def test_bts_kpop(self):
        from app.agents.intake_agent import _guess_category_from_url

        assert _guess_category_from_url(
            "https://weverse.io/bts/shop",
            {"title": "BTS Butter Album"},
        ) == "kpop_merch"

    def test_taylor_swift(self):
        from app.agents.intake_agent import _guess_category_from_url

        result = _guess_category_from_url(
            "https://mercari.com/item/123",
            {"title": "Taylor Swift Eras Tour T-Shirt"},
        )
        assert result == "taylor_swift"

    def test_lego_bricklink(self):
        from app.agents.intake_agent import _guess_category_from_url

        result = _guess_category_from_url(
            "https://bricklink.com/v2/catalog/something",
            {"title": "LEGO Set 10255"},
        )
        assert result == "lego"

    def test_funko(self):
        from app.agents.intake_agent import _guess_category_from_url

        result = _guess_category_from_url(
            "https://ebay.com/itm/123",
            {"title": "Funko Pop! Vinyl Spider-Man"},
        )
        assert result == "funko"

    def test_unknown_category(self):
        from app.agents.intake_agent import _guess_category_from_url

        result = _guess_category_from_url(
            "https://example.com/item",
            {"title": "Generic Item"},
        )
        assert result is None

    def test_mfc_anime_figures(self):
        from app.agents.intake_agent import _guess_category_from_url

        result = _guess_category_from_url(
            "https://myfigurecollection.net/item/12345",
            {"title": "Some Figure"},
        )
        assert result == "anime_figures"


# ---------------------------------------------------------------------------
# process_url_import async tests
# ---------------------------------------------------------------------------

class TestProcessUrlImport:
    """Tests for process_url_import()."""

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        from app.agents.intake_agent import process_url_import

        result = await process_url_import("not-a-url")
        assert "Invalid URL" in result.rationale[0]

    @pytest.mark.asyncio
    async def test_firecrawl_not_configured(self):
        from app.agents.intake_agent import process_url_import

        with patch("app.agents.intake_agent.get_db_pool", return_value=None):
            with patch("app.lib.firecrawl_client.FIRECRAWL_API_KEY", ""):
                result = await process_url_import("https://ebay.com/itm/123")

        assert result.identification_method == "url_import_failed"
        assert any("not configured" in r for r in result.rationale)

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        from app.agents.intake_agent import process_url_import

        mock_scrape = AsyncMock(return_value={
            "extract": {
                "title": "BTS Butter Album Sealed",
                "price": 35.0,
                "currency": "USD",
                "condition": "New",
                "image_urls": ["https://img.example.com/bts.jpg"],
                "seller_name": "kpop_seller",
                "category_hint": "kpop",
                "attributes": {"sealed": True},
            },
            "markdown": "# BTS Butter Album",
            "metadata": {"title": "BTS Butter Album"},
        })

        with patch("app.agents.intake_agent.get_db_pool", return_value=None):
            with patch("app.lib.firecrawl_client.scrape_url", mock_scrape):
                with patch("app.lib.firecrawl_client.configured", return_value=True):
                    result = await process_url_import("https://ktown4u.com/item/123")

        assert result.name == "BTS Butter Album Sealed"
        assert result.identification_method == "url_import"
        assert result.category_id == "kpop_merch"
        assert result.image_url == "https://img.example.com/bts.jpg"
        assert result.estimated_price is not None
        assert result.attributes.get("seller_name") == "kpop_seller"
        assert result.attributes.get("sealed") is True

    @pytest.mark.asyncio
    async def test_fallback_to_metadata(self):
        from app.agents.intake_agent import process_url_import

        mock_scrape = AsyncMock(return_value={
            "extract": None,
            "markdown": "# Some page content with items",
            "metadata": {
                "title": "Taylor Swift Eras Tour Poster",
                "og:title": "Taylor Swift Eras Tour Poster",
                "og:image": "https://img.example.com/ts.jpg",
            },
        })

        with patch("app.agents.intake_agent.get_db_pool", return_value=None):
            with patch("app.lib.firecrawl_client.scrape_url", mock_scrape):
                with patch("app.lib.firecrawl_client.configured", return_value=True):
                    result = await process_url_import("https://mercari.com/item/456")

        assert result.name == "Taylor Swift Eras Tour Poster"
        assert result.image_url == "https://img.example.com/ts.jpg"
        assert result.category_id == "taylor_swift"
        assert any("metadata" in r for r in result.rationale)

    @pytest.mark.asyncio
    async def test_scrape_returns_none(self):
        from app.agents.intake_agent import process_url_import

        mock_scrape = AsyncMock(return_value=None)

        with patch("app.agents.intake_agent.get_db_pool", return_value=None):
            with patch("app.lib.firecrawl_client.scrape_url", mock_scrape):
                with patch("app.lib.firecrawl_client.configured", return_value=True):
                    result = await process_url_import("https://ebay.com/itm/123")

        assert result.identification_method == "url_import_failed"
        assert any("no data" in r for r in result.rationale)

    @pytest.mark.asyncio
    async def test_user_hints_override(self):
        from app.agents.intake_agent import process_url_import

        mock_scrape = AsyncMock(return_value={
            "extract": {"title": "Some Item", "price": 10.0, "currency": "EUR"},
            "markdown": "content",
        })

        with patch("app.agents.intake_agent.get_db_pool", return_value=None):
            with patch("app.lib.firecrawl_client.scrape_url", mock_scrape):
                with patch("app.lib.firecrawl_client.configured", return_value=True):
                    result = await process_url_import(
                        "https://ebay.com/itm/123",
                        user_hints={"category": "funko", "name": "My Funko", "condition": "Mint"},
                    )

        assert result.category_id == "funko"
        assert result.name == "My Funko"
        assert result.attributes["condition"] == "Mint"
        assert result.category_confidence == 1.0

    @pytest.mark.asyncio
    async def test_exception_does_not_leak(self):
        from app.agents.intake_agent import process_url_import

        with patch("app.agents.intake_agent.get_db_pool", return_value=None):
            with patch(
                "app.lib.firecrawl_client.scrape_url",
                AsyncMock(side_effect=RuntimeError("internal error details")),
            ):
                with patch("app.lib.firecrawl_client.configured", return_value=True):
                    result = await process_url_import("https://ebay.com/itm/123")

        assert result.identification_method == "url_import_failed"
        # Verify no internal error details leak
        for r in result.rationale:
            assert "internal error details" not in r


# ---------------------------------------------------------------------------
# Router endpoint tests (via TestClient)
# ---------------------------------------------------------------------------

class TestIntakeUrlEndpoint:
    """Tests for POST /intake/url via HTTP."""

    def test_url_required(self, client):
        r = client.post("/intake/url", json={})
        assert r.status_code == 422

    def test_empty_url_rejected(self, client):
        r = client.post("/intake/url", json={"url": ""})
        assert r.status_code == 422

    def test_non_http_url_rejected(self, client):
        r = client.post("/intake/url", json={"url": "ftp://example.com"})
        assert r.status_code == 400

    def test_ssrf_private_ip_rejected(self, client):
        """SSRF protection blocks private/internal IPs."""
        r = client.post("/intake/url", json={"url": "http://169.254.169.254/latest/meta-data/"})
        assert r.status_code == 400
        assert "private" in r.json()["detail"]["message"].lower() or "internal" in r.json()["detail"]["message"].lower()

    def test_ssrf_localhost_rejected(self, client):
        """SSRF protection blocks localhost."""
        r = client.post("/intake/url", json={"url": "http://127.0.0.1:8000/healthz"})
        assert r.status_code == 400

    def test_valid_url_accepted(self, client):
        mock_result = MagicMock()
        mock_result.name = "Test Item"
        mock_result.category_id = "funko"
        mock_result.category_confidence = 0.7
        mock_result.subtype_id = None
        mock_result.attributes = {"source_url": "https://ebay.com/itm/123"}
        mock_result.identification_method = "url_import"
        mock_result.barcode = None
        mock_result.barcode_type = None
        mock_result.taxonomy_version = "v1.0"
        mock_result.taxonomy_confidence = 0.7
        mock_result.suggested_corrections = []
        mock_result.estimated_price = 14.99
        mock_result.price_source = "listing_ebay"
        mock_result.price_band = None
        mock_result.image_url = None
        mock_result.rationale = ["URL provided", "Detected: ebay"]
        mock_result.catalog_match_id = None
        mock_result.catalog_match_key = None
        mock_result.chain_of_thought = None
        mock_result.catalog_miss = False
        mock_result.alternatives = []
        mock_result.field_confidence = {}

        with patch(
            "app.agents.intake_router.process_url_import",
            AsyncMock(return_value=mock_result),
        ), patch(
            "app.agents.intake_router.validate_url",
            return_value="https://ebay.com/itm/123",
        ):
            r = client.post("/intake/url", json={"url": "https://ebay.com/itm/123"})

        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Test Item"
        assert data["identification_method"] == "url_import"

    def test_url_with_hints(self, client):
        mock_result = MagicMock()
        mock_result.name = "Custom Name"
        mock_result.category_id = "kpop_merch"
        mock_result.category_confidence = 1.0
        mock_result.subtype_id = None
        mock_result.attributes = {}
        mock_result.identification_method = "url_import"
        mock_result.barcode = None
        mock_result.barcode_type = None
        mock_result.taxonomy_version = "v1.0"
        mock_result.taxonomy_confidence = 1.0
        mock_result.suggested_corrections = []
        mock_result.estimated_price = None
        mock_result.price_source = None
        mock_result.price_band = None
        mock_result.image_url = None
        mock_result.rationale = []
        mock_result.catalog_match_id = None
        mock_result.catalog_match_key = None
        mock_result.chain_of_thought = None
        mock_result.catalog_miss = False
        mock_result.alternatives = []
        mock_result.field_confidence = {}

        with patch(
            "app.agents.intake_router.process_url_import",
            AsyncMock(return_value=mock_result),
        ), patch(
            "app.agents.intake_router.validate_url",
            return_value="https://ktown4u.com/item/123",
        ):
            r = client.post("/intake/url", json={
                "url": "https://ktown4u.com/item/123",
                "category": "kpop_merch",
                "name": "Custom Name",
                "condition": "Mint",
            })

        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Custom Name"
        assert data["category_id"] == "kpop_merch"
