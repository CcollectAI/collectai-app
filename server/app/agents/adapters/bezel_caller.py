"""
Bezel marketplace adapter for the Marketplace Aggregation Agent.

Bezel (getbezel.com) is a trusted watch marketplace app. This adapter
scrapes Bezel search results for active and sold watch listings using
their shop API endpoint with an HTML scrape fallback.

Covers: watches only (Bezel is a specialist watch marketplace).

Env vars:
    BEZEL_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import bezel_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

BEZEL_SOURCE_RELIABILITY = 0.80
BEZEL_SOLD_RELIABILITY = 0.85

# Bezel shop API endpoint (publicly accessible JSON)
BEZEL_API_URL = "https://shop.getbezel.com/api/listings"

# Fallback: scrape search page
BEZEL_SEARCH_PAGE = "https://www.getbezel.com/search?q={query}"

# Bezel only covers watches
SUPPORTED_CATEGORIES = ["watches"]


def _normalize_listing(item: Dict[str, Any], is_sold: bool = False) -> Dict[str, Any]:
    """Normalize a Bezel listing to the standard MarketHit format."""
    item_id = item.get("id") or item.get("listingId") or ""
    title_parts = []
    if item.get("brand"):
        title_parts.append(item["brand"])
    if item.get("model"):
        title_parts.append(item["model"])
    if item.get("referenceNumber"):
        title_parts.append(f"Ref. {item['referenceNumber']}")
    title = " ".join(title_parts) if title_parts else item.get("title") or item.get("name") or "Unknown Watch"

    price = 0.0
    for price_field in ("price", "askingPrice", "soldPrice", "listPrice"):
        val = item.get(price_field)
        if val:
            try:
                price = float(val)
                if price > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Handle nested price objects (e.g. {"amount": 5000, "currency": "USD"})
    if price == 0 and isinstance(item.get("price"), dict):
        try:
            price = float(item["price"].get("amount", 0))
        except (ValueError, TypeError):
            pass

    # Image URL
    image_url = ""
    if item.get("imageUrl"):
        image_url = item["imageUrl"]
    elif item.get("images") and isinstance(item["images"], list):
        first = item["images"][0]
        if isinstance(first, str):
            image_url = first
        elif isinstance(first, dict):
            image_url = first.get("url") or first.get("medium") or ""
    elif item.get("thumbnailUrl"):
        image_url = item["thumbnailUrl"]

    # Condition
    condition = item.get("condition") or item.get("conditionLabel")
    if isinstance(condition, dict):
        condition = condition.get("label") or condition.get("name")

    # URL
    slug = item.get("slug") or item.get("permalink") or ""
    if slug:
        url = f"https://www.getbezel.com/listing/{slug}"
    elif item_id:
        url = f"https://www.getbezel.com/listing/{item_id}"
    else:
        url = BEZEL_SEARCH_PAGE.format(query="")

    return {
        "source": "bezel",
        "raw_id": f"bezel-{item_id}",
        "title": str(title)[:500],
        "price": price,
        "currency": "USD",
        "source_price": price,
        "source_currency": "USD",
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": item.get("soldAt") or item.get("soldDate") if is_sold else None,
    }


class BezelCaller:
    """Async Bezel adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("BEZEL_ENABLED", "true").lower() == "true"
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
                    "Accept": "application/json, text/html",
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
        """Search Bezel for active watch listings."""
        if not self.configured:
            return []

        try:
            bezel_circuit.check()
        except CircuitOpenError:
            logger.warning("Bezel circuit open -- skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                BEZEL_API_URL,
                params={
                    "query": query,
                    "limit": str(min(limit, 20)),
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("listings") or data.get("results") or data.get("data") or data.get("items", [])
                if isinstance(data, list):
                    items = data
                bezel_circuit.record_success()
                return [_normalize_listing(item, is_sold=False) for item in items[:limit]]

            # Fallback to scraping search page if API returns non-200
            logger.debug("Bezel API returned %d, attempting page scrape", resp.status_code)
            return await self._scrape_search(query, limit)

        except Exception as exc:
            bezel_circuit.record_failure()
            logger.warning("Bezel search error: %s", exc)
            return []

    async def _scrape_search(
        self, query: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape Bezel search page for listings."""
        try:
            client = await self._client()
            url = BEZEL_SEARCH_PAGE.format(query=quote_plus(query))
            resp = await client.get(url)
            if resp.status_code != 200:
                bezel_circuit.record_failure()
                return []

            bezel_circuit.record_success()

            text = resp.text
            results = []

            # Look for listing patterns in the HTML
            listing_pattern = re.compile(r'/listing/([a-zA-Z0-9_-]+)')
            price_pattern = re.compile(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')

            ids_found = list(dict.fromkeys(listing_pattern.findall(text)))[:limit]
            prices = price_pattern.findall(text)

            for i, listing_id in enumerate(ids_found):
                price = 0.0
                if i < len(prices):
                    try:
                        price = float(prices[i].replace(",", ""))
                    except ValueError:
                        pass

                results.append({
                    "source": "bezel",
                    "raw_id": f"bezel-{listing_id}",
                    "title": query,
                    "price": price,
                    "currency": "USD",
                    "source_price": price,
                    "source_currency": "USD",
                    "url": f"https://www.getbezel.com/listing/{listing_id}",
                    "condition": None,
                    "image_url": "",
                    "is_sold": False,
                })

            return results[:limit]

        except Exception as exc:
            bezel_circuit.record_failure()
            logger.warning("Bezel scrape error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Bezel for sold/completed watch listings."""
        if not self.configured:
            return []

        try:
            bezel_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                BEZEL_API_URL,
                params={
                    "query": query,
                    "limit": str(min(limit, 20)),
                    "status": "sold",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("listings") or data.get("results") or data.get("data") or data.get("items", [])
                if isinstance(data, list):
                    items = data
                bezel_circuit.record_success()
                return [_normalize_listing(item, is_sold=True) for item in items[:limit]]

            # 2026-04-23 silent-failure sweep: never record success on non-200.
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                bezel_circuit.record_failure()
                logger.warning("Bezel sold_comps HTTP %d — circuit failure", resp.status_code)
            return []

        except Exception as exc:
            bezel_circuit.record_failure()
            logger.warning("Bezel sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                BEZEL_API_URL,
                params={"query": "rolex", "limit": "1"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
