"""
Mavin.io price aggregator adapter for the Marketplace Aggregation Agent.

Mavin.io aggregates eBay sold item data with enhanced analytics —
average selling price, price trends, volume data, and grading info.
Provides high-quality sold price data across virtually all collectible categories.

This is a high-reliability source (0.80) because it uses actual eBay sold data
but with better deduplication and statistical analysis than raw eBay sold comps.

Env vars:
    MAVIN_API_KEY  - Mavin.io API key
    MAVIN_ENABLED  - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from workers.circuit_breaker import mavin_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

MAVIN_SOURCE_RELIABILITY = 0.80
MAVIN_SOLD_RELIABILITY = 0.85

# Mavin.io API endpoints
MAVIN_SEARCH_URL = "https://mavin.io/search"
MAVIN_API_URL = "https://mavin.io/api/v1/search"


def _normalize_result(item: Dict[str, Any], is_sold: bool = True) -> Dict[str, Any]:
    """Normalize a Mavin.io result to the standard MarketHit format."""
    item_id = item.get("id") or item.get("itemId") or ""
    title = item.get("title") or item.get("name") or "Unknown"

    # Mavin provides aggregated price data
    price = 0.0
    for price_field in ("averagePrice", "soldPrice", "price", "estimatedValue"):
        val = item.get(price_field)
        if val:
            try:
                price = float(val)
                if price > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Price range from Mavin analytics
    price_low = item.get("lowPrice") or item.get("priceRangeLow")
    price_high = item.get("highPrice") or item.get("priceRangeHigh")

    # Image
    image_url = item.get("imageUrl") or item.get("image") or item.get("thumbnailUrl") or ""

    # Volume data
    sold_count = item.get("soldCount") or item.get("numberOfSales") or 0

    # Condition/grade
    condition = item.get("condition") or item.get("grade")

    return {
        "source": "mavin",
        "raw_id": f"mavin-{item_id}",
        "title": title[:500],
        "price": price,
        "currency": "USD",
        "source_price": price,
        "source_currency": "USD",
        "url": item.get("url") or f"https://mavin.io/item/{item_id}" if item_id else MAVIN_SEARCH_URL,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": item.get("lastSoldDate") or item.get("dateSold"),
        "price_low": float(price_low) if price_low else None,
        "price_high": float(price_high) if price_high else None,
        "sold_count": int(sold_count) if sold_count else None,
    }


class MavinCaller:
    """Async Mavin.io adapter for the marketplace aggregation agent."""

    def __init__(self, api_key: Optional[str] = None, enabled: Optional[bool] = None):
        import os
        self._api_key = api_key or os.getenv("MAVIN_API_KEY", "")
        self._enabled = enabled if enabled is not None else os.getenv("MAVIN_ENABLED", "true").lower() == "true"
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers=headers,
                follow_redirects=True,
            )
        return self._http

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Mavin.io for price data (primarily sold data)."""
        if not self.configured:
            return []

        try:
            mavin_circuit.check()
        except CircuitOpenError:
            logger.warning("Mavin circuit open — skipping")
            return []

        try:
            client = await self._client()

            # Try API endpoint first
            if self._api_key:
                resp = await client.get(
                    MAVIN_API_URL,
                    params={
                        "q": query,
                        "limit": str(min(limit, 30)),
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("results") or data.get("items") or data.get("data", [])
                    mavin_circuit.record_success()
                    return [_normalize_result(item, is_sold=True) for item in items[:limit]]

            # Fallback: scrape search page
            resp = await client.get(
                MAVIN_SEARCH_URL,
                params={"q": query, "bt": "sold"},
            )

            if resp.status_code == 200:
                mavin_circuit.record_success()
                return self._parse_search_page(resp.text, query, limit)

            mavin_circuit.record_success()
            return []

        except Exception as exc:
            mavin_circuit.record_failure()
            logger.warning("Mavin search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, query: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Mavin.io search results from HTML."""
        results = []

        # Mavin shows sold items with prices in a structured format
        # Look for price and title patterns
        item_blocks = re.findall(
            r'class="sold-item"[^>]*>.*?href="([^"]*)".*?<img[^>]*src="([^"]*)".*?'
            r'class="item-title"[^>]*>([^<]+)</.*?'
            r'class="item-price"[^>]*>\$?([\d,]+\.?\d*)',
            html,
            re.DOTALL,
        )

        for url, image, title, price_str in item_blocks[:limit]:
            try:
                price = float(price_str.replace(",", ""))
            except ValueError:
                price = 0.0

            item_id = re.search(r'/item/([^/?]+)', url)
            rid = item_id.group(1) if item_id else title[:30].replace(" ", "_")

            results.append({
                "source": "mavin",
                "raw_id": f"mavin-{rid}",
                "title": title.strip()[:500],
                "price": price,
                "currency": "USD",
                "source_price": price,
                "source_currency": "USD",
                "url": f"https://mavin.io{url}" if url.startswith("/") else url,
                "condition": None,
                "image_url": image,
                "is_sold": True,
            })

        # Fallback: simpler price extraction
        if not results:
            prices = re.findall(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', html)
            for i, price_str in enumerate(prices[:limit]):
                try:
                    price = float(price_str.replace(",", ""))
                except ValueError:
                    continue
                if price > 0:
                    results.append({
                        "source": "mavin",
                        "raw_id": f"mavin-search-{i}",
                        "title": query,
                        "price": price,
                        "currency": "USD",
                        "source_price": price,
                        "source_currency": "USD",
                        "url": MAVIN_SEARCH_URL,
                        "condition": None,
                        "image_url": "",
                        "is_sold": True,
                    })

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Mavin.io is primarily a sold-price aggregator — search IS sold comps."""
        return await self.search(query, category, limit)

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(MAVIN_SEARCH_URL, params={"q": "test"})
            return resp.status_code in (200, 301, 302)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
