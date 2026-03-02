"""
GouletPens marketplace adapter for the Marketplace Aggregation Agent.

GouletPens (gouletpens.com) is the leading fountain pen specialty retailer in
the US. This adapter scrapes GouletPens search results for active listing
prices in USD.

Covers: pens only.

Env vars:
    GOULETPENS_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import gouletpens_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

GOULETPENS_SOURCE_RELIABILITY = 0.80

# GouletPens search URL
GOULETPENS_SEARCH_URL = "https://www.gouletpens.com/search"

# GouletPens only covers pens
SUPPORTED_CATEGORIES = ["pens"]


def _parse_price(price_str: str) -> float:
    """Parse a USD price string like '$29.95' or '29.95' into a float."""
    if not price_str:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", price_str)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_listing(
    sku: str,
    title: str,
    price: float,
    image_url: str,
    url: str,
    condition: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a GouletPens listing to the standard MarketHit format."""
    return {
        "source": "gouletpens",
        "raw_id": f"goulet-{sku}",
        "title": title[:500],
        "price": price,
        "currency": "USD",
        "url": url or f"{GOULETPENS_SEARCH_URL}?q={quote_plus(title[:100])}",
        "condition": condition or "New",
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class GouletPensCaller:
    """Async GouletPens adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("GOULETPENS_ENABLED", "true").lower() == "true"
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
                    "Accept-Language": "en-US,en;q=0.9",
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
        """Search GouletPens for fountain pen listings."""
        if not self.configured:
            return []

        try:
            gouletpens_circuit.check()
        except CircuitOpenError:
            logger.warning("GouletPens circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                GOULETPENS_SEARCH_URL,
                params={"q": query},
            )

            if resp.status_code != 200:
                gouletpens_circuit.record_failure()
                logger.warning("GouletPens search returned %d", resp.status_code)
                return []

            gouletpens_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            gouletpens_circuit.record_failure()
            logger.warning("GouletPens search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse GouletPens search results from HTML.

        GouletPens search page contains product cards with:
        - Product links (e.g. /products/pilot-vanishing-point)
        - SKU or product ID embedded in data attributes
        - Titles in heading or product-name elements
        - Prices in USD (e.g. $29.95)
        - Image URLs from <img> tags (cdn.shopify.com)
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract product links — GouletPens uses /products/<slug>
        product_pattern = re.compile(
            r'href="(/products/([a-zA-Z0-9_-]+))"',
        )

        # Price pattern — USD prices like "$29.95" or "$185.00"
        price_pattern = re.compile(
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        )

        # Title pattern — product titles
        title_pattern = re.compile(
            r'class="[^"]*(?:product[_-]?(?:title|name)|card[_-]?title|item[_-]?name)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # SKU pattern — data-sku or data-product-id attributes
        sku_pattern = re.compile(
            r'data-(?:sku|product-id|variant-id)="([^"]+)"',
            re.IGNORECASE,
        )

        # Image pattern — Shopify CDN images
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://cdn\.shopify\.com/[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Extract product links (deduplicated)
        product_matches = list(dict.fromkeys(
            [(m[0], m[1]) for m in product_pattern.findall(html)]
        ))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        skus = sku_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        for i, (href, slug) in enumerate(product_matches):
            # Title
            title = titles[i].strip() if i < len(titles) else slug.replace("-", " ").title()

            # Price
            price = 0.0
            if i < len(prices):
                price = _parse_price(prices[i])

            # SKU — prefer explicit data attribute, fall back to slug
            sku = skus[i] if i < len(skus) else slug

            # Image
            image_url = images[i] if i < len(images) else ""

            # Full URL
            url = f"https://www.gouletpens.com{href}" if href.startswith("/") else href

            results.append(
                _normalize_listing(sku, title, price, image_url, url)
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        GouletPens is a retailer and does not expose sold/historical pricing.
        Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                GOULETPENS_SEARCH_URL,
                params={"q": "pilot"},
            )
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
