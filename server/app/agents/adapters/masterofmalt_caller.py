"""
Master of Malt marketplace adapter for the Marketplace Aggregation Agent.

Master of Malt (masterofmalt.com) is one of the UK's largest online whisky
retailers with extensive listings for whisky, bourbon, rum, and other spirits.
This adapter scrapes search results to extract retail pricing data in GBP.

Covers: whiskey only.

Env vars:
    MASTEROFMALT_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import masterofmalt_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

MASTEROFMALT_SOURCE_RELIABILITY = 0.80

# Master of Malt search URL
MASTEROFMALT_SEARCH_URL = "https://www.masterofmalt.com/search/"

# Categories that Master of Malt covers
SUPPORTED_CATEGORIES = [
    "whiskey",
]

# GBP to EUR fallback rate
_FALLBACK_GBP_TO_EUR = 1.17


def _convert_gbp_to_eur(gbp_price: float) -> float:
    """Convert GBP price to EUR using live rates with fallback."""
    try:
        from pipelines.import_common import to_eur
        return to_eur(gbp_price, "GBP")
    except Exception:
        return round(gbp_price * _FALLBACK_GBP_TO_EUR, 2)


def _parse_gbp_price(text: str) -> float:
    """Extract a GBP price from text like '\u00a3120', '\u00a31,250.00', 'GBP 450'."""
    if not text:
        return 0.0

    patterns = [
        r'\xc2?\xa3([\d,]+(?:\.\d{2})?)',       # \u00a3 symbol (raw bytes)
        r'\u00a3([\d,]+(?:\.\d{2})?)',           # \u00a3 symbol (unicode)
        r'&pound;([\d,]+(?:\.\d{2})?)',          # HTML entity
        r'GBP\s*([\d,]+(?:\.\d{2})?)',           # GBP prefix
        r'gbp\s*([\d,]+(?:\.\d{2})?)',           # gbp lowercase
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (ValueError, TypeError):
                continue

    return 0.0


def _normalize_listing(
    product_id: str,
    title: str,
    gbp_price: float,
    condition: Optional[str],
    image_url: str,
    product_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a Master of Malt listing to the standard MarketHit format."""
    eur_price = _convert_gbp_to_eur(gbp_price)

    if product_url and product_url.startswith("/"):
        item_url = f"https://www.masterofmalt.com{product_url}"
    elif product_url and product_url.startswith("http"):
        item_url = product_url
    elif product_id:
        item_url = f"https://www.masterofmalt.com/search/?search={product_id}"
    else:
        item_url = MASTEROFMALT_SEARCH_URL

    return {
        "source": "masterofmalt",
        "raw_id": f"mom-{product_id}",
        "title": title[:500],
        "price": eur_price,
        "currency": "EUR",
        "source_price": gbp_price,
        "source_currency": "GBP",
        "url": item_url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class MasterOfMaltCaller:
    """Async Master of Malt adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("MASTEROFMALT_ENABLED", "true").lower() == "true"
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-GB,en;q=0.9",
                },
                follow_redirects=True,
            )
        return self._http

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Master of Malt for whisky/spirits listings."""
        if not self.configured:
            return []

        try:
            masterofmalt_circuit.check()
        except CircuitOpenError:
            logger.warning("Master of Malt circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                MASTEROFMALT_SEARCH_URL,
                params={"search": query},
            )

            if resp.status_code in (429, 503):
                masterofmalt_circuit.record_failure()
                logger.warning("Master of Malt returned %d", resp.status_code)
                return []

            if resp.status_code != 200:
                masterofmalt_circuit.record_failure()
                logger.warning("Master of Malt search returned %d", resp.status_code)
                return []

            masterofmalt_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            masterofmalt_circuit.record_failure()
            logger.warning("Master of Malt search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Master of Malt search results from HTML.

        Master of Malt search pages contain:
        - Product URLs with slug-based IDs
        - Whisky/spirit names and distillery info
        - Prices in GBP (e.g., \u00a3120.00)
        - Product images
        - ABV, age, volume info
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract product URLs and IDs
        # MoM URLs like /whiskies/macallan/macallan-18-year-old/
        product_url_pattern = re.compile(
            r'href="(/(?:whiskies|bourbon|rum|spirits|gin|vodka|brandy|tequila)/[^"]+)"',
            re.IGNORECASE,
        )

        # Price pattern — GBP prices
        price_pattern = re.compile(
            r'(?:\xa3|&pound;|GBP)\s*([\d,]+(?:\.\d{2})?)',
            re.IGNORECASE,
        )

        # Title pattern
        title_pattern = re.compile(
            r'class="[^"]*(?:product-name|product-title|item-title|boxBgR)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Broader title from product links
        title_link_pattern = re.compile(
            r'href="/(?:whiskies|bourbon|rum|spirits)/[^"]*"[^>]*>\s*([^<]+?)\s*<',
            re.IGNORECASE,
        )

        # Image pattern
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:masterofmalt|mom)[^"]*\.(jpg|jpeg|png|webp))"',
            re.IGNORECASE,
        )

        # Broader image pattern
        img_pattern_broad = re.compile(
            r'<img[^>]+src="(https?://[^"]*product[^"]*\.(jpg|jpeg|png|webp))"',
            re.IGNORECASE,
        )

        # Extract product URLs (used as IDs)
        product_urls = list(dict.fromkeys(product_url_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        if not titles:
            titles = title_link_pattern.findall(html)
        prices = price_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]
        if not images:
            images = [m[0] for m in img_pattern_broad.findall(html)]

        for i, product_url in enumerate(product_urls):
            # Generate a product ID from the URL slug
            slug = product_url.strip("/").split("/")[-1] if product_url else str(i)
            product_id = re.sub(r'[^a-zA-Z0-9-]', '', slug)[:80]

            # Title
            title = titles[i].strip() if i < len(titles) else slug.replace("-", " ").title()

            # Price (GBP)
            gbp_price = 0.0
            if i < len(prices):
                try:
                    gbp_price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # Whisky is always "New" (sealed bottle)
            condition = "New/Sealed"

            results.append(
                _normalize_listing(
                    product_id, title, gbp_price, condition, image_url,
                    product_url=product_url,
                )
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        Master of Malt is a retail storefront and does not expose sold/completed
        order history publicly. Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                MASTEROFMALT_SEARCH_URL,
                params={"search": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
