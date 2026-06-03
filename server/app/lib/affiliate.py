"""
Affiliate Link Builder.

Generates affiliate-tagged URLs for each marketplace so that Sparrow Collect
earns commissions when users click through and buy.

Each tagged URL also carries a per-click **sub-ID** so that, when a network
reports a confirmed sale, the conversion can be attributed back to the exact
deal / user that generated it (see docs/AFFILIATE_SWITCH_ON.md → reconciliation).
The sub-ID is carried in each network's tracking field:
  - eBay Partner Network → ``customid``
  - everyone else        → ``utm_content``
Callers that have a stable identifier (e.g. the deal_id) should pass it as
``subid``; otherwise it defaults to the brand slug ``sparrow``.

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
    url, source = build_affiliate_url(listing_url, "ebay", subid=deal_id)
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

# Fallback sub-ID when the caller has no per-click identifier to attribute.
_DEFAULT_SUBID = "sparrow"


def build_affiliate_url(
    original_url: str,
    source: str,
    subid: str | None = None,
) -> tuple[str, str]:
    """Build an affiliate-tagged URL for a marketplace listing.

    Args:
        original_url: The original listing URL.
        source: Marketplace identifier ('ebay', 'tcgplayer', 'cardmarket', etc.)
        subid: Optional per-click tracking token (e.g. a deal_id) used for
            conversion attribution. Carried in ``customid`` (eBay) or
            ``utm_content`` (all others). Defaults to the brand slug.

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

    sub = subid or _DEFAULT_SUBID
    source_lower = source.lower()

    if source_lower == "ebay" and EBAY_AFFILIATE_CAMPAIGN_ID:
        return _tag_ebay(original_url, sub), "ebay_partner_network"

    if source_lower == "tcgplayer" and TCGPLAYER_AFFILIATE_ID:
        return _tag_tcgplayer(original_url, sub), "tcgplayer_affiliate"

    if source_lower == "cardmarket" and CARDMARKET_AFFILIATE_ID:
        return _tag_cardmarket(original_url, sub), "cardmarket_affiliate"

    if source_lower == "mercari" and MERCARI_AFFILIATE_ID:
        return _tag_mercari(original_url, sub), "mercari"

    if source_lower == "discogs" and DISCOGS_AFFILIATE_TOKEN:
        return _tag_discogs(original_url, sub), "discogs"

    if source_lower == "stockx" and STOCKX_AFFILIATE_ID:
        return _tag_stockx(original_url, sub), "stockx"

    if source_lower == "bricklink" and BRICKLINK_AFFILIATE_ID:
        return _tag_bricklink(original_url, sub), "bricklink"

    if source_lower == "whatnot" and WHATNOT_AFFILIATE_ID:
        return _tag_whatnot(original_url, sub), "whatnot"

    if source_lower == "catawiki" and CATAWIKI_AFFILIATE_ID:
        return _tag_catawiki(original_url, sub), "catawiki"

    if source_lower == "keh" and KEH_AFFILIATE_ID:
        return _tag_keh(original_url, sub), "keh"

    if source_lower == "mpb" and MPB_AFFILIATE_ID:
        return _tag_mpb(original_url, sub), "mpb"

    if source_lower == "masterofmalt" and MASTEROFMALT_AFFILIATE_ID:
        return _tag_masterofmalt(original_url, sub), "masterofmalt"

    if source_lower == "popmart" and POPMART_AFFILIATE_ID:
        return _tag_popmart(original_url, sub), "popmart"

    if source_lower == "drop" and DROP_AFFILIATE_ID:
        return _tag_drop(original_url, sub), "drop"

    if source_lower == "chrono24" and CHRONO24_AFFILIATE_ID:
        return _tag_chrono24(original_url, sub), "chrono24"

    if source_lower == "amiami" and AMIAMI_AFFILIATE_ID:
        return _tag_amiami(original_url, sub), "amiami"

    # No affiliate programme available for this source
    return original_url, ""


def _tag_ebay(url: str, subid: str) -> str:
    """Append eBay Partner Network (EPN) params."""
    return _append_params(url, {
        "campid": EBAY_AFFILIATE_CAMPAIGN_ID,
        "customid": subid,
        "toolid": "10001",
        "mkevt": "1",
    })


def _tag_tcgplayer(url: str, subid: str) -> str:
    """Append TCGPlayer affiliate params."""
    return _append_params(url, {
        "partner": TCGPLAYER_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "deal_agent",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_cardmarket(url: str, subid: str) -> str:
    """Append Cardmarket referrer param."""
    return _append_params(url, {
        "referrer": CARDMARKET_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_content": subid,
    })


def _tag_mercari(url: str, subid: str) -> str:
    """Append Mercari (Impact/Awin) affiliate params."""
    return _append_params(url, {
        "ref": "sparrow",
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_discogs(url: str, subid: str) -> str:
    """Append Discogs affiliate params."""
    return _append_params(url, {
        "anv": "sparrow",
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_content": subid,
    })


def _tag_stockx(url: str, subid: str) -> str:
    """Append StockX (Impact) affiliate params."""
    return _append_params(url, {
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_bricklink(url: str, subid: str) -> str:
    """Append BrickLink referral params."""
    return _append_params(url, {
        "ref": "sparrow",
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_content": subid,
    })


def _tag_whatnot(url: str, subid: str) -> str:
    """Append WhatNot (Impact.com) affiliate params."""
    return _append_params(url, {
        "ref": WHATNOT_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_catawiki(url: str, subid: str) -> str:
    """Append Catawiki (Partnerize) affiliate params."""
    return _append_params(url, {
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
        "chn": CATAWIKI_AFFILIATE_ID,
    })


def _tag_keh(url: str, subid: str) -> str:
    """Append KEH Camera (ShareASale) affiliate params."""
    return _append_params(url, {
        "aid": KEH_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_mpb(url: str, subid: str) -> str:
    """Append MPB (FlexOffers/Sovrn) affiliate params."""
    return _append_params(url, {
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
        "ref": MPB_AFFILIATE_ID,
    })


def _tag_masterofmalt(url: str, subid: str) -> str:
    """Append MasterOfMalt (Affiliate Future) affiliate params."""
    return _append_params(url, {
        "af": MASTEROFMALT_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_popmart(url: str, subid: str) -> str:
    """Append PopMart (Yeesshh/Digidip) affiliate params."""
    return _append_params(url, {
        "ref": POPMART_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_drop(url: str, subid: str) -> str:
    """Append Drop.com (FlexOffers) affiliate params."""
    return _append_params(url, {
        "ref": DROP_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_chrono24(url: str, subid: str) -> str:
    """Append Chrono24 (Direct partnership) affiliate params."""
    return _append_params(url, {
        "ref": CHRONO24_AFFILIATE_ID,
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
    })


def _tag_amiami(url: str, subid: str) -> str:
    """Append AmiAmi (Sovrn Commerce) affiliate params."""
    return _append_params(url, {
        "utm_source": "sparrow",
        "utm_medium": "affiliate",
        "utm_campaign": "smart_deal",
        "utm_content": subid,
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
