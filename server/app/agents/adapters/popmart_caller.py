"""
PopMart marketplace adapter for the Marketplace Aggregation Agent.

PopMart (popmart.com) is the leading blind box / designer toy marketplace,
offering retail pricing for collectible designer toys and blind box series.
This adapter scrapes PopMart search results to extract active listing prices,
primarily in USD.

Covers global collectible categories: blind_box, designer_toys.

Env vars:
    POPMART_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import popmart_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

POPMART_SOURCE_RELIABILITY = 0.75

# PopMart search URL
POPMART_SEARCH_URL = "https://www.popmart.com/search"

# PopMart item detail URL prefix
POPMART_DETAIL_URL = "https://www.popmart.com/products"

# Categories that PopMart excels in
SUPPORTED_CATEGORIES = [
    "blind_box",
    "designer_toys",
]

# USD to EUR fallback rate (used when import_common is unavailable)
_FALLBACK_USD_TO_EUR = 0.92


def _convert_usd_to_eur(usd_price: float) -> float:
    """Convert USD price to EUR using live rates with fallback."""
    try:
        from pipelines.import_common import to_eur
        return to_eur(usd_price, "USD")
    except Exception:
        return round(usd_price * _FALLBACK_USD_TO_EUR, 2)


def _parse_price(price_str: str) -> float:
    """Parse a USD/CNY price string like '$12.99' or '¥89.00' into a float."""
    if not price_str:
        return 0.0
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[$¥€£,\s]", "", price_str)
    # Remove any non-numeric characters except dot
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_listing(
    product_id: str,
    title: str,
    usd_price: float,
    condition: Optional[str],
    image_url: str,
) -> Dict[str, Any]:
    """Normalize a PopMart listing to the standard MarketHit format."""
    eur_price = _convert_usd_to_eur(usd_price)
    item_url = f"{POPMART_DETAIL_URL}/{product_id}" if product_id else POPMART_SEARCH_URL

    return {
        "source": "popmart",
        "raw_id": f"popmart-{product_id}",
        "title": title[:500],
        "price": eur_price,
        "currency": "EUR",
        "source_price": usd_price,
        "source_currency": "USD",
        "url": item_url,
        "condition": condition or "New",
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class PopMartCaller:
    """Async PopMart adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("POPMART_ENABLED", "true").lower() == "true"
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
        """Search PopMart for active listings."""
        if not self.configured:
            return []

        try:
            popmart_circuit.check()
        except CircuitOpenError:
            logger.warning("PopMart circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                POPMART_SEARCH_URL,
                params={
                    "keyword": query,
                },
            )

            if resp.status_code != 200:
                popmart_circuit.record_failure()
                logger.warning("PopMart search returned %d", resp.status_code)
                return []

            popmart_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            popmart_circuit.record_failure()
            logger.warning("PopMart search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse PopMart search results from HTML.

        PopMart's search page contains product cards with:
        - Product IDs in links (e.g., /products/slug-123)
        - Titles in heading/card elements
        - Prices in USD (e.g., $12.99)
        - Image URLs from <img> tags
        All PopMart items are new/retail, so condition is always "New".
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract product IDs from links
        product_id_pattern = re.compile(
            r'/products/([a-zA-Z0-9_-]+)',
        )

        # Price pattern — USD prices like "$12.99" or "$129.00"
        price_pattern = re.compile(
            r'\$\s*(\d{1,4}(?:\.\d{1,2})?)',
        )

        # Title pattern — PopMart product titles
        title_pattern = re.compile(
            r'class="[^"]*(?:product-title|product-name|card-title|item-title)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern — PopMart image URLs
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:popmart|cdn)[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Extract unique product IDs
        product_ids = list(dict.fromkeys(product_id_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        for i, product_id in enumerate(product_ids):
            # Title
            title = titles[i].strip() if i < len(titles) else f"PopMart item {product_id}"

            # Price
            usd_price = 0.0
            if i < len(prices):
                try:
                    usd_price = float(prices[i])
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # All PopMart items are new retail products
            results.append(
                _normalize_listing(product_id, title, usd_price, "New", image_url)
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        PopMart is a retail site — it does not expose sold history.
        Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                POPMART_SEARCH_URL,
                params={"keyword": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
