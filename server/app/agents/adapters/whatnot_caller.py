"""
WhatNot marketplace adapter for the Marketplace Aggregation Agent.

WhatNot is a live-auction platform popular for TCG cards, Funko Pops,
sports cards, and designer toys. This adapter scrapes WhatNot search
results to extract recently sold auction prices.

Env vars:
    WHATNOT_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import whatnot_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

WHATNOT_SOURCE_RELIABILITY = 0.65
WHATNOT_SOLD_RELIABILITY = 0.75

# WhatNot search URL
WHATNOT_SEARCH_URL = "https://www.whatnot.com/search"

# Categories that WhatNot excels in
SUPPORTED_CATEGORIES = [
    "pokemon",
    "mtg",
    "yugioh",
    "lorcana",
    "funko",
    "sportscards",
    "designer_toys",
    "hot_toys",
    "anime_figures",
    "kpop_merch",
    "vintage",
]


def _normalize_listing(item: Dict[str, Any], is_sold: bool = False) -> Dict[str, Any]:
    """Normalize a WhatNot listing to the standard MarketHit format."""
    item_id = item.get("id") or item.get("listingId") or ""
    title = item.get("title") or item.get("name") or "Unknown"
    price = 0.0

    for price_field in ("currentPrice", "soldPrice", "startingPrice", "price"):
        val = item.get(price_field)
        if val:
            try:
                price = float(val)
                if price > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Image
    image_url = ""
    if item.get("imageUrl"):
        image_url = item["imageUrl"]
    elif item.get("images") and isinstance(item["images"], list):
        image_url = item["images"][0] if isinstance(item["images"][0], str) else ""

    # Condition — WhatNot listings don't always specify condition
    condition = item.get("condition")

    return {
        "source": "whatnot",
        "raw_id": f"whatnot-{item_id}",
        "title": title[:500],
        "price": price,
        "currency": "USD",
        "source_price": price,
        "source_currency": "USD",
        "url": f"https://www.whatnot.com/listing/{item_id}" if item_id else WHATNOT_SEARCH_URL,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": item.get("soldAt") or item.get("endedAt"),
    }


class WhatNotCaller:
    """Async WhatNot adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("WHATNOT_ENABLED", "true").lower() == "true"
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
        """Search WhatNot for active/upcoming listings."""
        if not self.configured:
            return []

        try:
            whatnot_circuit.check()
        except CircuitOpenError:
            logger.warning("WhatNot circuit open — skipping")
            return []

        try:
            client = await self._client()

            # Try the internal API first
            resp = await client.get(
                "https://api.whatnot.com/api/v1/search",
                params={
                    "query": query,
                    "limit": str(min(limit, 30)),
                    "type": "listing",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("results") or data.get("listings") or data.get("data", [])
                whatnot_circuit.record_success()
                return [_normalize_listing(item) for item in items[:limit]]

            # Fallback: scrape search page. 2026-04-23 silent-failure sweep —
            # only record success on 200, otherwise trip the circuit.
            resp = await client.get(
                WHATNOT_SEARCH_URL,
                params={"query": query},
            )
            if resp.status_code != 200:
                if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                    whatnot_circuit.record_failure()
                    logger.warning("WhatNot fallback HTTP %d — circuit failure", resp.status_code)
                return []
            whatnot_circuit.record_success()

            # Parse listings from HTML/JSON embedded in page
            results = self._parse_search_page(resp.text, query, limit)
            return results

        except Exception as exc:
            whatnot_circuit.record_failure()
            logger.warning("WhatNot search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, query: str, limit: int) -> List[Dict[str, Any]]:
        """Parse WhatNot search results from HTML."""
        results = []

        # Look for listing IDs and prices in the page
        listing_pattern = re.compile(r'/listing/([a-zA-Z0-9-]+)')
        price_pattern = re.compile(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)')

        ids = list(set(listing_pattern.findall(html)))[:limit]
        prices = price_pattern.findall(html)

        for i, listing_id in enumerate(ids):
            price = 0.0
            if i < len(prices):
                try:
                    price = float(prices[i].replace(",", ""))
                except ValueError:
                    pass

            results.append({
                "source": "whatnot",
                "raw_id": f"whatnot-{listing_id}",
                "title": query,
                "price": price,
                "currency": "USD",
                "source_price": price,
                "source_currency": "USD",
                "url": f"https://www.whatnot.com/listing/{listing_id}",
                "condition": None,
                "image_url": "",
                "is_sold": False,
            })

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search WhatNot for sold/completed auction results."""
        if not self.configured:
            return []

        try:
            whatnot_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                "https://api.whatnot.com/api/v1/search",
                params={
                    "query": query,
                    "limit": str(min(limit, 30)),
                    "type": "sold",
                    "status": "completed",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("results") or data.get("listings") or data.get("data", [])
                whatnot_circuit.record_success()
                return [_normalize_listing(item, is_sold=True) for item in items[:limit]]

            # 2026-04-23 silent-failure sweep: never record success on non-200.
            # Fallback re-queries search() which has its own circuit logic.
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                whatnot_circuit.record_failure()
                logger.warning("WhatNot sold_comps HTTP %d — circuit failure", resp.status_code)
            results = await self.search(query, category, limit)
            for r in results:
                r["is_sold"] = True
            return results

        except Exception as exc:
            whatnot_circuit.record_failure()
            logger.warning("WhatNot sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(WHATNOT_SEARCH_URL, params={"query": "test"})
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
