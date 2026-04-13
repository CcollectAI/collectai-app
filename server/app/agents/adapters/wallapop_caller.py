"""
Wallapop marketplace adapter for the Marketplace Aggregation Agent.

Wallapop is Spain's largest second-hand marketplace.
Uses the public v3 search API — no API key required.

Primary region: Spain
Prices in EUR.

Env vars:
    WALLAPOP_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from workers.circuit_breaker import wallapop_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

WALLAPOP_SOURCE_RELIABILITY = 0.60

WALLAPOP_API_URL = "https://api.wallapop.com/api/v3/general/search"

# Default coordinates: Madrid city centre
WALLAPOP_DEFAULT_LAT = "40.4168"
WALLAPOP_DEFAULT_LNG = "-3.7038"


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Wallapop item to the standard MarketHit format."""
    item_id = item.get("id") or ""
    title = item.get("content") or item.get("title") or "Unknown"

    # Price
    price = 0.0
    currency = "EUR"
    price_val = item.get("price")
    if isinstance(price_val, (int, float)):
        price = float(price_val)
    elif isinstance(price_val, dict):
        price = float(price_val.get("amount") or 0)
        currency = price_val.get("currency") or "EUR"
    elif isinstance(price_val, str):
        try:
            price = float(price_val)
        except (ValueError, TypeError):
            pass

    # Currency override at top level
    item_currency = item.get("currency")
    if isinstance(item_currency, str) and item_currency:
        currency = item_currency.upper()

    # Images
    image_url = ""
    images = item.get("images") or []
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            image_url = (
                first.get("original") or first.get("large")
                or first.get("medium") or first.get("small")
                or first.get("url") or ""
            )
        elif isinstance(first, str):
            image_url = first

    # URL — construct from web_slug
    url = ""
    web_slug = item.get("web_slug") or item.get("slug") or ""
    if web_slug:
        url = f"https://es.wallapop.com/item/{web_slug}"
    elif item_id:
        url = f"https://es.wallapop.com/item/{item_id}"

    # Condition
    condition = item.get("condition") or None
    if isinstance(condition, dict):
        condition = condition.get("title") or condition.get("name") or None

    return {
        "source": "wallapop",
        "raw_id": f"wallapop-{item_id}",
        "title": title[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class WallapopCaller:
    """Async Wallapop adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os

        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("WALLAPOP_ENABLED", "true").lower() == "true"
        )
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
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
        """Search Wallapop for active listings."""
        if not self.configured:
            return []

        try:
            wallapop_circuit.check()
        except CircuitOpenError:
            logger.warning("Wallapop circuit open — skipping")
            return []

        try:
            client = await self._client()

            params = {
                "keywords": query,
                "filters_source": "default_filters",
                "latitude": WALLAPOP_DEFAULT_LAT,
                "longitude": WALLAPOP_DEFAULT_LNG,
            }

            resp = await client.get(WALLAPOP_API_URL, params=params)

            if resp.status_code == 200:
                data = resp.json()
                # Wallapop nests results under search_objects or items
                items = (
                    data.get("search_objects")
                    or data.get("items")
                    or data.get("results", [])
                )
                wallapop_circuit.record_success()
                return [_normalize_item(item) for item in items[:limit]]

            if resp.status_code in (429, 503):
                wallapop_circuit.record_failure()
                logger.warning("Wallapop API returned %d", resp.status_code)
                return []

            # Non-fatal status — still record as success to not trip breaker
            wallapop_circuit.record_success()
            return []

        except Exception as exc:
            wallapop_circuit.record_failure()
            logger.warning("Wallapop search error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Wallapop does not expose sold/completed listings — returns empty.

        The search() method returns active listings only.  For valuation
        purposes other adapters (eBay sold, Catawiki sold, Mavin) should
        be preferred.
        """
        return []

    async def health_check(self) -> bool:
        """Check if Wallapop API is reachable."""
        if not self.configured:
            return False
        try:
            client = await self._client()
            params = {
                "keywords": "test",
                "filters_source": "default_filters",
                "latitude": WALLAPOP_DEFAULT_LAT,
                "longitude": WALLAPOP_DEFAULT_LNG,
            }
            resp = await client.get(WALLAPOP_API_URL, params=params)
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
