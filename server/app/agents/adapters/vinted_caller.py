"""
Vinted marketplace adapter for the Marketplace Aggregation Agent.

Vinted is Europe's largest secondhand marketplace with strong coverage
for collectibles, vintage items, and fashion-adjacent collectibles.
This adapter searches Vinted's public search endpoint.

Primary region: Europe (FR, DE, IT, ES, NL, BE, AT, PL, CZ, LT)
Also available: US (limited), UK

Env vars:
    VINTED_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import vinted_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

VINTED_SOURCE_RELIABILITY = 0.65
VINTED_SOLD_RELIABILITY = 0.70

# Vinted search API — uses the web API endpoint
VINTED_DOMAINS = {
    "europe": "www.vinted.fr",
    "americas": "www.vinted.com",
    "other": "www.vinted.fr",
}

VINTED_SEARCH_PATH = "/api/v2/catalog/items"


def _normalize_item(item: Dict[str, Any], is_sold: bool = False) -> Dict[str, Any]:
    """Normalize a Vinted item to the standard MarketHit format."""
    item_id = item.get("id") or ""
    title = item.get("title") or "Unknown"

    price_obj = item.get("price") or item.get("total_item_price") or {}
    if isinstance(price_obj, dict):
        price = float(price_obj.get("amount") or 0)
        currency = price_obj.get("currency_code") or "EUR"
    elif isinstance(price_obj, (int, float)):
        price = float(price_obj)
        currency = "EUR"
    else:
        price = 0.0
        currency = "EUR"

    # Image URL
    image_url = ""
    photos = item.get("photos") or item.get("photo") or item.get("photos", [])
    if isinstance(photos, list) and photos:
        first = photos[0]
        image_url = first.get("url") or first.get("full_size_url") or "" if isinstance(first, dict) else str(first)
    elif isinstance(photos, dict):
        image_url = photos.get("url") or photos.get("full_size_url") or ""

    # Condition
    status = item.get("status_id")
    condition_map = {
        1: "New with tags",
        2: "New without tags",
        3: "Very Good",
        4: "Good",
        5: "Satisfactory",
    }
    condition = condition_map.get(status)

    # URL
    url = item.get("url") or f"https://www.vinted.fr/items/{item_id}"

    return {
        "source": "vinted",
        "raw_id": f"vinted-{item_id}",
        "title": title[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": item.get("sold_at") or item.get("updated_at") if is_sold else None,
    }


class VintedCaller:
    """Async Vinted adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("VINTED_ENABLED", "true").lower() == "true"
        self._http: Optional[httpx.AsyncClient] = None
        self._session_cookie: Optional[str] = None

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

    async def _ensure_session(self, domain: str) -> None:
        """Get a session cookie from Vinted (required for API access)."""
        if self._session_cookie:
            return
        try:
            client = await self._client()
            resp = await client.get(f"https://{domain}")
            # Extract session cookie
            for cookie_name in ("_vinted_fr_session", "_vinted_com_session", "vinted_session"):
                if cookie_name in client.cookies:
                    self._session_cookie = str(client.cookies[cookie_name])
                    break
        except Exception as e:
            logger.debug("Vinted session init failed: %s", e)

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search Vinted for active listings."""
        if not self.configured:
            return []

        try:
            vinted_circuit.check()
        except CircuitOpenError:
            logger.warning("Vinted circuit open — skipping")
            return []

        domain = VINTED_DOMAINS.get(region or "europe", VINTED_DOMAINS["europe"])

        try:
            client = await self._client()
            await self._ensure_session(domain)

            resp = await client.get(
                f"https://{domain}{VINTED_SEARCH_PATH}",
                params={
                    "search_text": query,
                    "per_page": str(min(limit, 30)),
                    "order": "relevance",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items") or data.get("catalog_items") or []
                vinted_circuit.record_success()
                return [_normalize_item(item) for item in items[:limit]]

            # Fallback: scrape search page HTML
            resp = await client.get(
                f"https://{domain}/catalog",
                params={"search_text": query},
            )
            vinted_circuit.record_success()
            return self._parse_search_page(resp.text, query, domain, limit)

        except Exception as exc:
            vinted_circuit.record_failure()
            logger.warning("Vinted search error: %s", exc)
            return []

    def _parse_search_page(
        self, html: str, query: str, domain: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Parse Vinted search results from HTML."""
        results = []
        item_pattern = re.compile(r'/items/(\d+)')
        price_pattern = re.compile(r'(\d+(?:[.,]\d{2})?)\s*€')

        ids = list(set(item_pattern.findall(html)))[:limit]
        prices = price_pattern.findall(html)

        for i, item_id in enumerate(ids):
            price = 0.0
            if i < len(prices):
                try:
                    price = float(prices[i].replace(",", "."))
                except ValueError:
                    pass

            results.append({
                "source": "vinted",
                "raw_id": f"vinted-{item_id}",
                "title": query,
                "price": price,
                "currency": "EUR",
                "source_price": price,
                "source_currency": "EUR",
                "url": f"https://{domain}/items/{item_id}",
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
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search Vinted for sold items (Vinted shows sold items with 'Sold' badge)."""
        if not self.configured:
            return []

        try:
            vinted_circuit.check()
        except CircuitOpenError:
            return []

        domain = VINTED_DOMAINS.get(region or "europe", VINTED_DOMAINS["europe"])

        try:
            client = await self._client()
            await self._ensure_session(domain)

            # Vinted API supports filtering by sold status
            resp = await client.get(
                f"https://{domain}{VINTED_SEARCH_PATH}",
                params={
                    "search_text": query,
                    "per_page": str(min(limit, 30)),
                    "order": "relevance",
                    "status_ids[]": "2",  # Sold/reserved
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items") or data.get("catalog_items") or []
                vinted_circuit.record_success()
                return [_normalize_item(item, is_sold=True) for item in items[:limit]]

            vinted_circuit.record_success()
            return []

        except Exception as exc:
            vinted_circuit.record_failure()
            logger.warning("Vinted sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get("https://www.vinted.fr")
            return resp.status_code in (200, 301, 302)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
