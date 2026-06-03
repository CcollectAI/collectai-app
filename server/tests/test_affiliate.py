"""
Tests for app/lib/affiliate.py — Affiliate Link Builder.

Covers:
  - eBay Partner Network URL tagging
  - TCGPlayer affiliate URL tagging
  - Cardmarket affiliate URL tagging
  - Unknown source passthrough
  - URL with existing query params preserved
  - Empty/missing credentials → no tagging
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


class TestEbayAffiliate:
    def test_ebay_url_tagged(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert "campid=CAMP123" in url
            assert "customid=sparrow" in url
            assert source == "ebay_partner_network"

    def test_ebay_subid_attribution(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url(
                "https://www.ebay.com/itm/12345", "ebay", subid="deal-abc-123"
            )
            # Per-click sub-ID rides in customid so a conversion report can be
            # joined back to the originating deal/user.
            assert "customid=deal-abc-123" in url
            assert "customid=sparrow" not in url
            assert source == "ebay_partner_network"

    def test_ebay_no_credentials(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", ""):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert url == "https://www.ebay.com/itm/12345"
            assert source == ""

    def test_preserves_existing_params(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, _ = build_affiliate_url("https://www.ebay.com/itm/12345?foo=bar", "ebay")
            assert "foo=bar" in url
            assert "campid=CAMP123" in url


class TestTcgplayerAffiliate:
    def test_tcgplayer_url_tagged(self):
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", "PARTNER456"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.tcgplayer.com/product/12345", "tcgplayer")
            assert "partner=PARTNER456" in url
            assert "utm_source=sparrow" in url
            assert source == "tcgplayer_affiliate"

    def test_tcgplayer_subid_in_utm_content(self):
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", "PARTNER456"):
            from app.lib.affiliate import build_affiliate_url

            url, _ = build_affiliate_url(
                "https://www.tcgplayer.com/product/12345", "tcgplayer", subid="deal-xyz"
            )
            # Non-eBay networks carry the sub-ID in utm_content.
            assert "utm_content=deal-xyz" in url

    def test_tcgplayer_no_credentials(self):
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", ""):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.tcgplayer.com/product/12345", "tcgplayer")
            assert url == "https://www.tcgplayer.com/product/12345"
            assert source == ""


class TestCardmarketAffiliate:
    def test_cardmarket_url_tagged(self):
        with patch("app.lib.affiliate.CARDMARKET_AFFILIATE_ID", "REF789"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.cardmarket.com/en/Pokemon/Products/12345", "cardmarket")
            assert "referrer=REF789" in url
            assert source == "cardmarket_affiliate"

    def test_cardmarket_no_credentials(self):
        with patch("app.lib.affiliate.CARDMARKET_AFFILIATE_ID", ""):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.cardmarket.com/en/Pokemon/Products/12345", "cardmarket")
            assert url == "https://www.cardmarket.com/en/Pokemon/Products/12345"
            assert source == ""


class TestUnknownSource:
    def test_firecrawl_passthrough(self):
        from app.lib.affiliate import build_affiliate_url

        url, source = build_affiliate_url("https://www.somesite.com/listing/123", "firecrawl")
        assert url == "https://www.somesite.com/listing/123"
        assert source == ""

    def test_empty_source(self):
        from app.lib.affiliate import build_affiliate_url

        url, source = build_affiliate_url("https://example.com", "")
        assert url == "https://example.com"
        assert source == ""


class TestCaseSensitivity:
    def test_ebay_case_insensitive(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "eBay")
            assert "campid=CAMP123" in url
            assert source == "ebay_partner_network"


class TestSchemeValidation:
    """Reject non-HTTP(S) URLs to prevent open redirect."""

    def test_javascript_scheme_rejected(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("javascript:alert(1)", "ebay")
            assert url == "javascript:alert(1)"
            assert source == ""

    def test_data_scheme_rejected(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("data:text/html,<h1>hi</h1>", "ebay")
            assert url == "data:text/html,<h1>hi</h1>"
            assert source == ""

    def test_http_scheme_allowed(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("http://www.ebay.com/itm/12345", "ebay")
            assert "campid=CAMP123" in url
            assert source == "ebay_partner_network"

    def test_https_scheme_allowed(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert "campid=CAMP123" in url
            assert source == "ebay_partner_network"


class TestEdgeCases:
    """Edge cases: None, empty, malformed URLs."""

    def test_empty_url(self):
        from app.lib.affiliate import build_affiliate_url

        url, source = build_affiliate_url("", "ebay")
        assert url == ""
        assert source == ""

    def test_none_source(self):
        from app.lib.affiliate import build_affiliate_url

        url, source = build_affiliate_url("https://example.com", "")
        assert url == "https://example.com"
        assert source == ""
