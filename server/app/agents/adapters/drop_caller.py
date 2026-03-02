"""
Drop.com marketplace adapter for the Marketplace Aggregation Agent.

Drop.com (drop.com) is the main artisan keycap marketplace, specialising in
group-buy mechanical keyboard keycap sets. This adapter scrapes Drop search
results for active listing prices in USD.

Covers: keycaps only.

Env vars:
    DROP_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import drop_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

DROP_SOURCE_RELIABILITY = 0.75

# Drop search URL
DROP_SEARCH_URL = "https://drop.com/search"

# Drop only covers keycaps
SUPPORTED_CATEGORIES = ["keycaps"]


def _parse_price(price_str: str) -> float:
    """Parse a USD price string like '$59.99' or '59.99' into a float."""
    if not price_str:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", price_str)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_listing(
    product_id: str,
    title: str,
    price: float,
    image_url: str,
    url: str,
) -> Dict[str, Any]:
    """Normalize a Drop listing to the standard MarketHit format."""
    return {
        "source": "drop",
        "raw_id": f"drop-{product_id}",
        "title": title[:500],
        "price": price,
        "currency": "USD",
        "url": url or f"{DROP_SEARCH_URL}?query={quote_plus(title[:100])}",
        "condition": "New",
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class DropCaller:
    """Async Drop.com adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("DROP_ENABLED", "true").lower() == "true"
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
        """Search Drop.com for active keycap listings."""
        if not self.configured:
            return []

        try:
            drop_circuit.check()
        except CircuitOpenError:
            logger.warning("Drop circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                DROP_SEARCH_URL,
                params={"query": query},
            )

            if resp.status_code != 200:
                drop_circuit.record_failure()
                logger.warning("Drop search returned %d", resp.status_code)
                return []

            drop_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            drop_circuit.record_failure()
            logger.warning("Drop search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Drop search results from HTML.

        Drop's search page contains product cards with:
        - Product links (e.g. /buy/xxx-keycap-set)
        - Titles in heading or link elements
        - Prices in USD (e.g. $59.99)
        - Image URLs from <img> tags
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract product links — Drop uses /buy/<slug> format
        product_pattern = re.compile(
            r'href="(/buy/([a-zA-Z0-9_-]+))"',
        )

        # Price pattern — USD prices like "$59.99" or "$149.00"
        price_pattern = re.compile(
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        )

        # Title pattern — product titles in heading or link elements
        title_pattern = re.compile(
            r'class="[^"]*(?:product[_-]?(?:title|name)|card[_-]?title|item[_-]?name)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern — product images
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:massdrop|drop\.com|drop-assets)[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Extract product links
        product_matches = list(dict.fromkeys(
            [(m[0], m[1]) for m in product_pattern.findall(html)]
        ))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        for i, (href, slug) in enumerate(product_matches):
            # Title
            title = titles[i].strip() if i < len(titles) else slug.replace("-", " ").title()

            # Price
            price = 0.0
            if i < len(prices):
                price = _parse_price(prices[i])

            # Image
            image_url = images[i] if i < len(images) else ""

            # Full URL
            url = f"https://drop.com{href}" if href.startswith("/") else href

            results.append(
                _normalize_listing(slug, title, price, image_url, url)
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        Drop.com does not expose sold/completed group buy pricing publicly.
        Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                DROP_SEARCH_URL,
                params={"query": "keycap"},
            )
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
