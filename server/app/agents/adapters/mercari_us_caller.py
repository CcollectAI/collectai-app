"""
Mercari US marketplace adapter for the Marketplace Aggregation Agent.

Scrapes Mercari US search results for active and sold listings. Uses httpx
to fetch the Mercari search API (publicly accessible JSON endpoint).

Covers virtually all collectible categories — Mercari US has broad coverage
for secondhand collectibles, figures, cards, and vintage items.

Env vars:
    MERCARI_US_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import mercari_us_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

MERCARI_US_SOURCE_RELIABILITY = 0.70
MERCARI_US_SOLD_RELIABILITY = 0.75

# Mercari US search API endpoint (publicly accessible)
MERCARI_SEARCH_URL = "https://www.mercari.com/v1/api/items/search"

# Fallback: scrape search page
MERCARI_SEARCH_PAGE = "https://www.mercari.com/search/?keyword={query}"

# Item statuses
STATUS_ON_SALE = "on_sale"
STATUS_SOLD_OUT = "sold_out"


def _normalize_item(item: Dict[str, Any], is_sold: bool = False) -> Dict[str, Any]:
    """Normalize a Mercari US item to the standard MarketHit format."""
    item_id = item.get("id") or item.get("itemId") or ""
    name = item.get("name") or item.get("itemName") or "Unknown"
    price = 0.0

    # Price extraction — try multiple fields
    for price_field in ("price", "itemPrice", "sellerPrice"):
        val = item.get(price_field)
        if val:
            try:
                price = float(val)
                break
            except (ValueError, TypeError):
                continue

    # Image URL
    photos = item.get("photos") or item.get("itemPhotos") or []
    image_url = ""
    if photos and isinstance(photos, list):
        first = photos[0]
        if isinstance(first, str):
            image_url = first
        elif isinstance(first, dict):
            image_url = first.get("url") or first.get("medium") or ""
    elif item.get("thumbnails"):
        thumbs = item["thumbnails"]
        if isinstance(thumbs, list) and thumbs:
            image_url = thumbs[0] if isinstance(thumbs[0], str) else ""

    # Condition mapping
    condition_map = {
        1: "New",
        2: "Like New",
        3: "Good",
        4: "Fair",
        5: "Poor",
    }
    condition_id = item.get("itemConditionId") or item.get("condition", {}).get("id")
    condition = condition_map.get(condition_id, item.get("condition", {}).get("name")) if condition_id else None

    # Sold date
    sold_at = item.get("updated") or item.get("soldDate") if is_sold else None

    return {
        "source": "mercari_us",
        "raw_id": f"mercari-us-{item_id}",
        "title": name[:500],
        "price": price,
        "currency": "USD",
        "source_price": price,
        "source_currency": "USD",
        "url": f"https://www.mercari.com/us/item/{item_id}/",
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": sold_at,
    }


class MercariUSCaller:
    """Async Mercari US adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("MERCARI_US_ENABLED", "true").lower() == "true"
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
                    "Accept": "application/json",
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
        """Search Mercari US for active listings."""
        if not self.configured:
            return []

        try:
            mercari_us_circuit.check()
        except CircuitOpenError:
            logger.warning("Mercari US circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                MERCARI_SEARCH_URL,
                params={
                    "keyword": query,
                    "limit": str(min(limit, 30)),
                    "status": STATUS_ON_SALE,
                    "sort": "SORT_SCORE",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items") or data.get("data") or data.get("result", [])
                mercari_us_circuit.record_success()
                return [_normalize_item(item, is_sold=False) for item in items[:limit]]

            # Fallback to scraping search page if API returns non-200
            logger.debug("Mercari US API returned %d, attempting page scrape", resp.status_code)
            return await self._scrape_search(query, limit)

        except Exception as exc:
            mercari_us_circuit.record_failure()
            logger.warning("Mercari US search error: %s", exc)
            return []

    async def _scrape_search(
        self, query: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape Mercari search page for listings."""
        try:
            client = await self._client()
            url = MERCARI_SEARCH_PAGE.format(query=quote_plus(query))
            resp = await client.get(url)
            if resp.status_code != 200:
                mercari_us_circuit.record_failure()
                return []

            mercari_us_circuit.record_success()

            # Parse item IDs from the HTML — Mercari embeds JSON data
            text = resp.text
            results = []

            # Look for item patterns in the HTML
            item_pattern = re.compile(r'/us/item/(\w+)')
            price_pattern = re.compile(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)')
            title_pattern = re.compile(r'data-testid="ItemCell"[^>]*>.*?<p[^>]*>([^<]+)</p>', re.DOTALL)

            ids_found = list(set(item_pattern.findall(text)))[:limit]
            for item_id in ids_found:
                results.append({
                    "source": "mercari_us",
                    "raw_id": f"mercari-us-{item_id}",
                    "title": query,
                    "price": 0,
                    "currency": "USD",
                    "source_price": 0,
                    "source_currency": "USD",
                    "url": f"https://www.mercari.com/us/item/{item_id}/",
                    "condition": None,
                    "image_url": "",
                    "is_sold": False,
                })

            return results[:limit]

        except Exception as exc:
            mercari_us_circuit.record_failure()
            logger.warning("Mercari US scrape error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Mercari US for sold/completed listings."""
        if not self.configured:
            return []

        try:
            mercari_us_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                MERCARI_SEARCH_URL,
                params={
                    "keyword": query,
                    "limit": str(min(limit, 30)),
                    "status": STATUS_SOLD_OUT,
                    "sort": "SORT_SCORE",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items") or data.get("data") or data.get("result", [])
                mercari_us_circuit.record_success()
                return [_normalize_item(item, is_sold=True) for item in items[:limit]]

            mercari_us_circuit.record_success()
            return []

        except Exception as exc:
            mercari_us_circuit.record_failure()
            logger.warning("Mercari US sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                MERCARI_SEARCH_URL,
                params={"keyword": "test", "limit": "1"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
