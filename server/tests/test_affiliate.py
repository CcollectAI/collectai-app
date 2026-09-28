"""
Tests for app/lib/affiliate.py — Affiliate Link Builder.

Covers:
  - eBay Partner Network URL tagging
  - EPN rotation id per eBay site
  - Impact / Partnerize deep links
  - Programmes that do not exist or are unchecked stay untagged
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
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert "campid=5338000000" in url
            assert "customid=sparrow" in url
            assert source == "ebay_partner_network"

    def test_ebay_subid_attribution(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
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
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, _ = build_affiliate_url("https://www.ebay.com/itm/12345?foo=bar", "ebay")
            assert "foo=bar" in url
            assert "campid=5338000000" in url


IMPACT_LINK = "https://tcgplayer.pxf.io/c/1234567/1830156/21018"
PARTNERIZE_LINK = "https://prf.hn/click/camref:1100l4Abc"


class TestEbayRotationId:
    """EPN credits a click to the eBay site whose rotation id the link carries."""

    def test_ebay_com_carries_us_rotation(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, _ = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert "mkcid=1" in url
            assert "mkrid=711-53200-19255-0" in url

    def test_ebay_nl_carries_nl_rotation(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, _ = build_affiliate_url("https://www.ebay.nl/itm/12345", "ebay")
            assert "mkrid=1346-53482-19255-0" in url

    def test_ebay_benl_carries_be_rotation(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, _ = build_affiliate_url("https://benl.ebay.be/itm/12345", "ebay")
            assert "mkrid=1553-53471-19255-0" in url

    def test_unknown_ebay_site_untagged(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.pl/itm/12345", "ebay")
            assert url == "https://www.ebay.pl/itm/12345"
            assert source == ""

    def test_malformed_campaign_id_untagged(self):
        # A campaign id is 10 digits; anything else would build a dead link.
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "CAMP123"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert url == "https://www.ebay.com/itm/12345"
            assert source == ""


class TestImpactDeepLink:
    def test_tcgplayer_wrapped_in_tracking_link(self):
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", IMPACT_LINK):
            from urllib.parse import parse_qs, urlparse
            from app.lib.affiliate import build_affiliate_url

            dest = "https://www.tcgplayer.com/search/all/product?q=charizard&view=grid"
            url, source = build_affiliate_url(dest, "tcgplayer", subid="deal-xyz")
            assert url.startswith(IMPACT_LINK + "?")
            q = parse_qs(urlparse(url).query)
            # The shop URL survives intact, its own query included.
            assert q["u"] == [dest]
            assert q["subId1"] == ["deal-xyz"]
            assert source == "tcgplayer_affiliate"

    def test_bare_id_is_not_a_tracking_link(self):
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", "PARTNER456"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.tcgplayer.com/product/12345", "tcgplayer")
            assert url == "https://www.tcgplayer.com/product/12345"
            assert source == ""

    def test_tcgplayer_no_credentials(self):
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", ""):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.tcgplayer.com/product/12345", "tcgplayer")
            assert url == "https://www.tcgplayer.com/product/12345"
            assert source == ""


class TestPartnerizeDeepLink:
    def test_catawiki_pubref_before_destination(self):
        with patch("app.lib.affiliate.CATAWIKI_AFFILIATE_ID", PARTNERIZE_LINK):
            from urllib.parse import unquote
            from app.lib.affiliate import build_affiliate_url

            dest = "https://www.catawiki.com/en/l/12345?utm_x=1"
            url, source = build_affiliate_url(dest, "catawiki", subid="deal-1")
            assert url.startswith(PARTNERIZE_LINK + "/pubref:deal-1/destination:")
            assert unquote(url.split("/destination:", 1)[1]) == dest
            assert source == "catawiki"


class TestNoProgrammeOrUnchecked:
    def test_cardmarket_discogs_bricklink_never_tagged(self):
        from app.lib.affiliate import build_affiliate_url

        for src, u in [
            ("cardmarket", "https://www.cardmarket.com/en/Pokemon/Products/12345"),
            ("discogs", "https://www.discogs.com/sell/item/1"),
            ("bricklink", "https://www.bricklink.com/v2/catalog/catalogitem.page?S=75192-1"),
        ]:
            assert build_affiliate_url(u, src) == (u, "")

    def test_unchecked_network_untagged_even_when_set(self):
        with patch("app.lib.affiliate.CHRONO24_AFFILIATE_ID", "12345"):
            from app.lib.affiliate import build_affiliate_url

            u = "https://www.chrono24.com/rolex/ref-116610.htm"
            assert build_affiliate_url(u, "chrono24") == (u, "")

    def test_unchecked_network_set_value_is_logged(self, caplog):
        import app.lib.affiliate as aff

        aff._warned.discard("KEH_AFFILIATE_ID")
        with patch("app.lib.affiliate.KEH_AFFILIATE_ID", "12345"):
            with caplog.at_level("WARNING", logger="app.lib.affiliate"):
                aff.build_affiliate_url("https://www.keh.com/shop/x.html", "keh")
        assert "KEH_AFFILIATE_ID is set but its link format is unchecked" in caplog.text

    def test_checked_and_unchecked_are_disjoint(self):
        from app.lib.affiliate import _PROGRAMMES, _UNVERIFIED

        assert not set(_PROGRAMMES) & set(_UNVERIFIED)


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
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "eBay")
            assert "campid=5338000000" in url
            assert source == "ebay_partner_network"


class TestSchemeValidation:
    """Reject non-HTTP(S) URLs to prevent open redirect."""

    def test_javascript_scheme_rejected(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("javascript:alert(1)", "ebay")
            assert url == "javascript:alert(1)"
            assert source == ""

    def test_data_scheme_rejected(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("data:text/html,<h1>hi</h1>", "ebay")
            assert url == "data:text/html,<h1>hi</h1>"
            assert source == ""

    def test_http_scheme_allowed(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("http://www.ebay.com/itm/12345", "ebay")
            assert "campid=5338000000" in url
            assert source == "ebay_partner_network"

    def test_https_scheme_allowed(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
            assert "campid=5338000000" in url
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


class TestProgrammeChosenByHost:
    """A scraper row names the scraper, not the shop; the URL's host decides."""

    def test_crawl4ai_row_on_catawiki_is_tagged(self):
        with patch("app.lib.affiliate.CATAWIKI_AFFILIATE_ID", PARTNERIZE_LINK):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.catawiki.com/en/l/1", "crawl4ai")
            assert url.startswith(PARTNERIZE_LINK)
            assert source == "catawiki"

    def test_firecrawl_row_on_ebay_de_is_tagged(self):
        with patch("app.lib.affiliate.EBAY_AFFILIATE_CAMPAIGN_ID", "5338000000"):
            from app.lib.affiliate import build_affiliate_url

            url, source = build_affiliate_url("https://www.ebay.de/itm/1", "firecrawl")
            assert "mkrid=707-53477-19255-0" in url
            assert source == "ebay_partner_network"

    def test_source_label_does_not_tag_a_foreign_host(self):
        # Labelled tcgplayer, but it is a Mercari image: never wrap it in TCGplayer's link.
        with patch("app.lib.affiliate.TCGPLAYER_AFFILIATE_ID", IMPACT_LINK):
            from app.lib.affiliate import build_affiliate_url

            u = "https://u-mercari-images.mercdn.net/photos/m1_1.jpg"
            assert build_affiliate_url(u, "tcgplayer") == (u, "")
