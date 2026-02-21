"""
Shipping estimation service for cross-border marketplace listings.

Provides:
- estimate_shipping(from_region, to_region) → ShippingEstimate
- detect_listing_region(source, ships_from, url) → str | None
- is_cross_border(listing_region, user_region) → bool
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ShippingEstimate:
    """Estimated shipping cost for a listing."""
    min_cost_eur: float
    max_cost_eur: float
    is_domestic: bool
    domestic_only: bool
    disclaimer: Optional[str] = None


# Shipping cost matrix (EUR): (from_region, to_region) → (min, max)
_SHIPPING_MATRIX: dict[tuple[str, str], tuple[float, float]] = {
    # Domestic / same region
    ("americas", "americas"): (0, 5),
    ("europe", "europe"): (0, 5),
    ("japan", "japan"): (0, 5),
    ("korea", "korea"): (0, 5),
    ("oceania", "oceania"): (0, 5),
    # Americas ↔ Europe
    ("americas", "europe"): (15, 25),
    ("europe", "americas"): (15, 25),
    # Americas ↔ Japan
    ("americas", "japan"): (20, 30),
    ("japan", "americas"): (20, 30),
    # Europe ↔ Japan
    ("europe", "japan"): (20, 30),
    ("japan", "europe"): (20, 30),
    # Americas ↔ Oceania
    ("americas", "oceania"): (20, 35),
    ("oceania", "americas"): (20, 35),
    # Any ↔ Korea
    ("americas", "korea"): (15, 25),
    ("korea", "americas"): (15, 25),
    ("europe", "korea"): (15, 25),
    ("korea", "europe"): (15, 25),
    # Japan ↔ Korea (nearby)
    ("japan", "korea"): (10, 15),
    ("korea", "japan"): (10, 15),
    # Europe/Japan ↔ Oceania
    ("europe", "oceania"): (20, 35),
    ("oceania", "europe"): (20, 35),
    ("japan", "oceania"): (20, 35),
    ("oceania", "japan"): (20, 35),
    # Korea ↔ Oceania
    ("korea", "oceania"): (15, 25),
    ("oceania", "korea"): (15, 25),
}

_FALLBACK_SHIPPING = (15, 30)

_CROSS_BORDER_DISCLAIMER = "Customs/duties may apply"

# Domain → region mappings for URL-based detection
_DOMAIN_REGION_MAP: dict[str, str] = {
    ".co.jp": "japan",
    ".co.kr": "korea",
    ".kr": "korea",
    ".de": "europe",
    ".fr": "europe",
    ".nl": "europe",
    ".co.uk": "europe",
    ".it": "europe",
    ".es": "europe",
    ".com.au": "oceania",
    ".co.nz": "oceania",
}

# Known domestic-only source mappings
_SOURCE_REGION_MAP: dict[str, str] = {
    "mercari": "japan",
    "yahoo_auctions_jp": "japan",
    "yes24": "korea",
    "aladin": "korea",
    "ktown4u": "korea",
    "cokodive": "korea",
}


def estimate_shipping(
    from_region: Optional[str],
    to_region: Optional[str],
) -> ShippingEstimate:
    """Estimate shipping cost between two regions.

    Args:
        from_region: Listing origin region (americas/europe/japan/korea/oceania).
        to_region: User's region.

    Returns:
        ShippingEstimate with min/max EUR costs and domestic flag.
    """
    if not from_region or not to_region:
        mn, mx = _FALLBACK_SHIPPING
        return ShippingEstimate(
            min_cost_eur=mn,
            max_cost_eur=mx,
            is_domestic=False,
            domestic_only=False,
            disclaimer=_CROSS_BORDER_DISCLAIMER,
        )

    is_domestic = from_region == to_region
    key = (from_region, to_region)
    mn, mx = _SHIPPING_MATRIX.get(key, _FALLBACK_SHIPPING)

    return ShippingEstimate(
        min_cost_eur=mn,
        max_cost_eur=mx,
        is_domestic=is_domestic,
        domestic_only=False,
        disclaimer=None if is_domestic else _CROSS_BORDER_DISCLAIMER,
    )


def detect_listing_region(
    source: Optional[str] = None,
    ships_from: Optional[str] = None,
    url: Optional[str] = None,
) -> Optional[str]:
    """Try to detect the region a listing ships from.

    Priority:
    1. ships_from string (e.g. "US", "Japan", "DE")
    2. URL domain (e.g. .co.jp → japan)
    3. Source name (known domestic sources)
    4. None if unknown
    """
    # 1. Check ships_from
    if ships_from:
        sf = ships_from.strip().upper()
        # Direct country code mappings
        _country_to_region: dict[str, str] = {
            "US": "americas", "CA": "americas", "MX": "americas", "BR": "americas",
            "DE": "europe", "FR": "europe", "NL": "europe", "GB": "europe",
            "UK": "europe", "IT": "europe", "ES": "europe", "BE": "europe",
            "AT": "europe", "CH": "europe", "SE": "europe", "NO": "europe",
            "DK": "europe", "FI": "europe", "PL": "europe", "PT": "europe",
            "IE": "europe", "CZ": "europe",
            "JP": "japan", "JAPAN": "japan",
            "KR": "korea", "KOREA": "korea",
            "AU": "oceania", "NZ": "oceania",
        }
        region = _country_to_region.get(sf)
        if region:
            return region

    # 2. Check URL domain
    if url:
        url_lower = url.lower()
        for domain, region in _DOMAIN_REGION_MAP.items():
            if domain in url_lower:
                return region
        # .com defaults to americas for eBay/StockX-style sites
        if re.search(r'\.com/', url_lower) and not any(d in url_lower for d in _DOMAIN_REGION_MAP):
            return "americas"

    # 3. Check source name
    if source:
        src_lower = source.lower().replace(" ", "_")
        region = _SOURCE_REGION_MAP.get(src_lower)
        if region:
            return region

    return None


def is_cross_border(
    listing_region: Optional[str],
    user_region: Optional[str],
) -> bool:
    """Check if a listing is cross-border relative to the user's region."""
    if not listing_region or not user_region:
        return True  # unknown = assume cross-border
    return listing_region != user_region
