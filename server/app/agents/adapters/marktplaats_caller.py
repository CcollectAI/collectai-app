"""
Marktplaats marketplace adapter for the Marketplace Aggregation Agent.

Marktplaats is the Netherlands' largest classifieds platform (owned by eBay).
Uses the public LRP search API — no API key required.

Primary region: Netherlands
Prices in EUR.

Env vars:
    MARKTPLAATS_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import marktplaats_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

MARKTPLAATS_SOURCE_RELIABILITY = 0.60

MARKTPLAATS_API_URL = "https://www.marktplaats.nl/lrp/api/search"


def _normalize_listing(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Marktplaats listing to the standard MarketHit format."""
    item_id = item.get("itemId") or ""
    title = item.get("title") or "Unknown"

    # Price — Marktplaats stores price in cents or as float
    price = 0.0
    currency = "EUR"
    price_info = item.get("priceInfo") or {}
    if isinstance(price_info, dict):
        price_cents = price_info.get("priceCents")
        if isinstance(price_cents, (int, float)) and price_cents > 0:
            price = float(price_cents) / 100.0
        elif not price:
            # Fallback: priceType "FIXED" with price as euros
            price_eur = price_info.get("price") or price_info.get("priceEuros")
            if isinstance(price_eur, (int, float)) and price_eur > 0:
                price = float(price_eur)
    # Top-level price fallback
    if not price:
        top_price = item.get("price") or item.get("priceEur")
        if isinstance(top_price, (int, float)) and top_price > 0:
            price = float(top_price)

    # Images
    image_url = ""
    image_urls = item.get("imageUrls") or []
    if isinstance(image_urls, list) and image_urls:
        first = image_urls[0]
        image_url = first if isinstance(first, str) else ""
    # Some responses nest images differently
    if not image_url:
        pictures = item.get("pictures") or []
        if isinstance(pictures, list) and pictures:
            first = pictures[0]
            if isinstance(first, dict):
                image_url = first.get("url") or first.get("extraExtraLargeUrl") or ""
            elif isinstance(first, str):
                image_url = first

    # URL — construct from itemId or slug
    url = ""
    slug = item.get("slug") or item.get("url") or ""
    if slug and slug.startswith("http"):
        url = slug
    elif slug:
        url = f"https://www.marktplaats.nl{slug}" if slug.startswith("/") else f"https://www.marktplaats.nl/{slug}"
    elif item_id:
        url = f"https://www.marktplaats.nl/v/{item_id}"

    # Condition (not always present)
    condition = item.get("condition") or item.get("itemCondition") or None

    # Per-listing attributes. Marktplaats exposes sparse structured data;
    # harvest what's reliably there and defer the rest to future passes.
    listing_attrs: Dict[str, Any] = {}
    if condition:
        listing_attrs["condition"] = condition
    if item.get("brand"):
        listing_attrs["brand"] = item["brand"]
    seller = item.get("sellerInformation") or {}
    if isinstance(seller, dict) and seller.get("sellerType"):
        listing_attrs["seller_type"] = seller["sellerType"]

    return {
        "source": "marktplaats",
        "raw_id": f"marktplaats-{item_id}",
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
        "attributes": listing_attrs,
    }


class MarktplaatsCaller:
    """Async Marktplaats adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os

        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("MARKTPLAATS_ENABLED", "true").lower() == "true"
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
        """Search Marktplaats for active listings."""
        if not self.configured:
            return []

        try:
            marktplaats_circuit.check()
        except CircuitOpenError:
            logger.warning("Marktplaats circuit open — skipping")
            return []

        try:
            client = await self._client()

            params = {
                "query": query,
                "limit": min(limit, 30),
                "offset": 0,
            }

            resp = await client.get(MARKTPLAATS_API_URL, params=params)

            if resp.status_code == 200:
                data = resp.json()
                listings = data.get("listings") or data.get("items") or data.get("results", [])
                marktplaats_circuit.record_success()
                return [_normalize_listing(item) for item in listings[:limit]]

            # 2026-04-23 silent-failure sweep: trip the breaker on any
            # auth/rate/server error. Was special-casing only 429/503.
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                marktplaats_circuit.record_failure()
                logger.warning("Marktplaats API HTTP %d — circuit failure", resp.status_code)
            return []

        except Exception as exc:
            marktplaats_circuit.record_failure()
            logger.warning("Marktplaats search error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Marktplaats does not expose sold/completed listings — returns empty.

        The search() method returns active listings only.  For valuation
        purposes other adapters (eBay sold, Catawiki sold, Mavin) should
        be preferred.
        """
        return []

    async def health_check(self) -> bool:
        """Check if Marktplaats API is reachable."""
        if not self.configured:
            return False
        try:
            client = await self._client()
            params = {"query": "test", "limit": 1, "offset": 0}
            resp = await client.get(MARKTPLAATS_API_URL, params=params)
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
