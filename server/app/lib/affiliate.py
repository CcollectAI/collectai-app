"""
Affiliate Link Builder.

Generates affiliate-tagged URLs for each marketplace so that CollectAI earns
commissions when users click through and buy.

Supported programmes:
  - eBay Partner Network (EPN) — campid + customid params
  - TCGPlayer Affiliate — partner + utm params
  - Cardmarket Affiliate — referrer param
  - Mercari (Impact/Awin) — ref + utm params
  - Discogs Affiliate — anv + utm params
  - StockX (Impact) — utm params
  - BrickLink Referral — ref + utm params
  - WhatNot (Impact.com) — utm params, 1-3.5%
  - Catawiki (Partnerize) — utm params, ~7-10%
  - KEH Camera (ShareASale) — utm params, 1.6-3.2%
  - MPB (FlexOffers/Sovrn) — utm params, 2%
  - MasterOfMalt (Affiliate Future) — utm params, 5-7.66%
  - PopMart (Yeesshh/Digidip) — utm params, 1-8%
  - Drop.com (FlexOffers) — utm params, 1.6-2.4%
  - Chrono24 (Direct) — ref + utm params
  - AmiAmi (Sovrn Commerce) — utm params

URLs from unknown sources (e.g. Firecrawl scrape hits) are returned unchanged.

Usage:
    url, source = build_affiliate_url("https://www.ebay.com/itm/12345", "ebay")
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from app.config import (
    EBAY_AFFILIATE_CAMPAIGN_ID,
    TCGPLAYER_AFFILIATE_ID,
    CARDMARKET_AFFILIATE_ID,
    MERCARI_AFFILIATE_ID,
    DISCOGS_AFFILIATE_TOKEN,
    STOCKX_AFFILIATE_ID,
    BRICKLINK_AFFILIATE_ID,
    WHATNOT_AFFILIATE_ID,
    CATAWIKI_AFFILIATE_ID,
    KEH_AFFILIATE_ID,
    MPB_AFFILIATE_ID,
    MASTEROFMALT_AFFILIATE_ID,
    POPMART_AFFILIATE_ID,
    DROP_AFFILIATE_ID,
    CHRONO24_AFFILIATE_ID,
    AMIAMI_AFFILIATE_ID,
)

logger = logging.getLogger(__name__)


_ALLOWED_SCHEMES = {"http", "https"}


def build_affiliate_url(original_url: str, source: str) -> tuple[str, str]:
    """Build an affiliate-tagged URL for a marketplace listing.

    Args:
        original_url: The original listing URL.
        source: Marketplace identifier ('ebay', 'tcgplayer', 'cardmarket', etc.)

    Returns:
        Tuple of (affiliate_url, affiliate_source).
        If no affiliate programme is configured for the source,
        returns (original_url, '').
    """
    if not original_url or not source:
        return original_url or "", ""

    # Scheme validation — reject non-HTTP(S) URLs to prevent open redirect
    parsed = urlparse(original_url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        logger.warning("Rejected non-HTTP URL scheme: %s", parsed.scheme)
        return original_url, ""

    source_lower = source.lower()

    if source_lower == "ebay" and EBAY_AFFILIATE_CAMPAIGN_ID:
        return _tag_ebay(original_url), "ebay_partner_network"

    if source_lower == "tcgplayer" and TCGPLAYER_AFFILIATE_ID:
        return _tag_tcgplayer(original_url), "tcgplayer_affiliate"

    if source_lower == "cardmarket" and CARDMARKET_AFFILIATE_ID:
        return _tag_cardmarket(original_url), "cardmarket_affiliate"

    if source_lower == "mercari" and MERCARI_AFFILIATE_ID:
        return _tag_mercari(original_url), "mercari"

    if source_lower == "discogs" and DISCOGS_AFFILIATE_TOKEN:
        return _tag_discogs(original_url), "discogs"

    if source_lower == "stockx" and STOCKX_AFFILIATE_ID:
        return _tag_stockx(original_url), "stockx"

    if source_lower == "bricklink" and BRICKLINK_AFFILIATE_ID:
        return _tag_bricklink(original_url), "bricklink"

    if source_lower == "whatnot" and WHATNOT_AFFILIATE_ID:
        return _tag_whatnot(original_url), "whatnot"

    if source_lower == "catawiki" and CATAWIKI_AFFILIATE_ID:
        return _tag_catawiki(original_url), "catawiki"

    if source_lower == "keh" and KEH_AFFILIATE_ID:
        return _tag_keh(original_url), "keh"

    if source_lower == "mpb" and MPB_AFFILIATE_ID:
        return _tag_mpb(original_url), "mpb"

    if source_lower == "masterofmalt" and MASTEROFMALT_AFFILIATE_ID:
        return _tag_masterofmalt(original_url), "masterofmalt"

    if source_lower == "popmart" and POPMART_AFFILIATE_ID:
        return _tag_popmart(original_url), "popmart"

    if source_lower == "drop" and DROP_AFFILIATE_ID:
        return _tag_drop(original_url), "drop"

    if source_lower == "chrono24" and CHRONO24_AFFILIATE_ID:
        return _tag_chrono24(original_url), "chrono24"

    if source_lower == "amiami" and AMIAMI_AFFILIATE_ID:
        return _tag_amiami(original_url), "amiami"

    # No affiliate programme available for this source
    return original_url, ""


def _tag_ebay(url: str) -> str:
    """Append eBay Partner Network (EPN) params."""
    return _append_params(url, {
        "campid": EBAY_AFFILIATE_CAMPAIGN_ID,
        "customid": "collectai_deal",
        "toolid": "10001",
        "mkevt": "1",
    })


def _tag_tcgplayer(url: str) -> str:
    """Append TCGPlayer affiliate params."""
    return _append_params(url, {
        "partner": TCGPLAYER_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "deal_agent",
        "utm_campaign": "smart_deal",
    })


def _tag_cardmarket(url: str) -> str:
    """Append Cardmarket referrer param."""
    return _append_params(url, {
        "referrer": CARDMARKET_AFFILIATE_ID,
        "utm_source": "collectai",
    })


def _tag_mercari(url: str) -> str:
    """Append Mercari (Impact/Awin) affiliate params."""
    return _append_params(url, {
        "ref": "collectai",
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_discogs(url: str) -> str:
    """Append Discogs affiliate params."""
    return _append_params(url, {
        "anv": "collectai",
        "utm_source": "collectai",
        "utm_medium": "affiliate",
    })


def _tag_stockx(url: str) -> str:
    """Append StockX (Impact) affiliate params."""
    return _append_params(url, {
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_bricklink(url: str) -> str:
    """Append BrickLink referral params."""
    return _append_params(url, {
        "ref": "collectai",
        "utm_source": "collectai",
        "utm_medium": "affiliate",
    })


def _tag_whatnot(url: str) -> str:
    """Append WhatNot (Impact.com) affiliate params."""
    return _append_params(url, {
        "ref": WHATNOT_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_catawiki(url: str) -> str:
    """Append Catawiki (Partnerize) affiliate params."""
    return _append_params(url, {
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "chn": CATAWIKI_AFFILIATE_ID,
    })


def _tag_keh(url: str) -> str:
    """Append KEH Camera (ShareASale) affiliate params."""
    return _append_params(url, {
        "aid": KEH_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_mpb(url: str) -> str:
    """Append MPB (FlexOffers/Sovrn) affiliate params."""
    return _append_params(url, {
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "ref": MPB_AFFILIATE_ID,
    })


def _tag_masterofmalt(url: str) -> str:
    """Append MasterOfMalt (Affiliate Future) affiliate params."""
    return _append_params(url, {
        "af": MASTEROFMALT_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_popmart(url: str) -> str:
    """Append PopMart (Yeesshh/Digidip) affiliate params."""
    return _append_params(url, {
        "ref": POPMART_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_drop(url: str) -> str:
    """Append Drop.com (FlexOffers) affiliate params."""
    return _append_params(url, {
        "ref": DROP_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_chrono24(url: str) -> str:
    """Append Chrono24 (Direct partnership) affiliate params."""
    return _append_params(url, {
        "ref": CHRONO24_AFFILIATE_ID,
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
    })


def _tag_amiami(url: str) -> str:
    """Append AmiAmi (Sovrn Commerce) affiliate params."""
    return _append_params(url, {
        "utm_source": "collectai",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "ref": AMIAMI_AFFILIATE_ID,
    })


def _append_params(url: str, params: dict[str, str]) -> str:
    """Append query parameters to a URL, preserving existing params."""
    parsed = urlparse(url)
    existing = parse_qs(parsed.query, keep_blank_values=True)

    # Merge — new params override if key already exists
    for k, v in params.items():
        existing[k] = [v]

    # Rebuild query string
    flat: list[tuple[str, str]] = []
    for k, vals in existing.items():
        for v in vals:
            flat.append((k, v))

    new_query = urlencode(flat)
    return urlunparse(parsed._replace(query=new_query))
