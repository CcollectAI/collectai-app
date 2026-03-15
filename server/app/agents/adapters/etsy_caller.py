"""
Etsy marketplace adapter for the Marketplace Aggregation Agent.

Etsy is a large marketplace for handmade, vintage, and craft items.
This adapter uses the Etsy Open API v3 to search active listings.

Covers: vintage_toys, watches, pens, plush_collectibles, blind_box,
vintage_cameras, keycaps, diorama, custom_builds, scale_models,
designer_toys, funko (12 categories).

Env vars:
    ETSY_API_KEY - Etsy Open API v3 key
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.lib import etsy_client

logger = logging.getLogger(__name__)

ETSY_SOURCE_RELIABILITY = 0.75

# Categories that benefit from Etsy data
SUPPORTED_CATEGORIES = [
    "vintage_toys",
    "watches",
    "pens",
    "plush_collectibles",
    "blind_box",
    "vintage_cameras",
    "keycaps",
    "diorama",
    "custom_builds",
    "scale_models",
    "designer_toys",
    "funko",
]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an Etsy listing to the standard MarketHit format."""
    listing_id = listing.get("listing_id") or listing.get("id") or ""
    title = listing.get("title") or "Unknown"

    # Price: Etsy returns price as {amount, divisor, currency_code}
    price = 0.0
    currency = "USD"
    price_obj = listing.get("price")
    if isinstance(price_obj, dict):
        try:
            amount = float(price_obj.get("amount", 0))
            divisor = float(price_obj.get("divisor", 100))
            price = amount / divisor if divisor else 0.0
            currency = price_obj.get("currency_code", "USD")
        except (ValueError, TypeError):
            pass
    elif isinstance(price_obj, (int, float)):
        price = float(price_obj)

    # Image URL: images[0].url_570xN
    image_url = ""
    images = listing.get("images")
    if isinstance(images, list) and images:
        first_img = images[0]
        if isinstance(first_img, dict):
            image_url = first_img.get("url_570xN") or first_img.get("url_170x135") or ""
        elif isinstance(first_img, str):
            image_url = first_img

    # URL
    url = listing.get("url") or f"https://www.etsy.com/listing/{listing_id}"

    return {
        "source": "etsy",
        "raw_id": f"etsy-{listing_id}",
        "title": str(title)[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": None,
        "image_url": image_url,
        "is_sold": False,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class EtsyCaller:
    """Async Etsy adapter for the marketplace aggregation agent."""

    @property
    def configured(self) -> bool:
        return etsy_client.configured()

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search Etsy for active listings matching a query."""
        if not self.configured:
            return []

        raw = await etsy_client.search_listings(query, limit=limit)
        return [_normalize_listing(r) for r in raw[:limit]]

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Etsy API does not expose sold-only listings — returns empty."""
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            results = await etsy_client.search_listings("test", limit=1)
            return isinstance(results, list)
        except Exception:
            return False

    async def close(self) -> None:
        await etsy_client.close()
