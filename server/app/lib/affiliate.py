"""
Affiliate Link Builder.

Generates affiliate-tagged URLs for each marketplace so that CollectAI earns
commissions when users click through and buy.

Supported programmes:
  - eBay Partner Network (EPN) — campid + customid params
  - TCGPlayer Affiliate — partner + utm params
  - Cardmarket Affiliate — referrer param

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
