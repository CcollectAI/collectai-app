"""
Leboncoin marketplace adapter for the Marketplace Aggregation Agent.

Leboncoin is France's largest classifieds platform with a dedicated
"Collection" category (id 27) covering all types of collectibles.
Uses the public finder API with the embedded frontend API key.

Primary region: France
Prices in EUR.

Env vars:
    LEBONCOIN_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from workers.circuit_breaker import leboncoin_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

LEBONCOIN_SOURCE_RELIABILITY = 0.65
LEBONCOIN_SOLD_RELIABILITY = 0.60

# Leboncoin finder API (public, embedded in frontend JS)
LEBONCOIN_API_URL = "https://api.leboncoin.fr/finder/search"
LEBONCOIN_API_KEY = "ba0c2dad52b3ec"  # public key from frontend bundle

# Leboncoin "Collection" category
LEBONCOIN_COLLECTION_CATEGORY_ID = "27"


def _normalize_ad(ad: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Leboncoin ad to the standard MarketHit format."""
    ad_id = ad.get("list_id") or ad.get("id") or ""
    title = ad.get("subject") or ad.get("title") or "Unknown"

    # Price — Leboncoin stores price as a list of price objects or a flat int
    price = 0.0
    currency = "EUR"

    price_val = ad.get("price")
    if isinstance(price_val, list) and price_val:
        price = float(price_val[0])
    elif isinstance(price_val, (int, float)):
        price = float(price_val)

    # Attributes (condition, brand, colour, etc.). Leboncoin returns a flat
    # list of {key, value_label} pairs — harvest what the aggregator can
    # normalize downstream.
    condition = None
    listing_attrs: Dict[str, Any] = {}
    attributes = ad.get("attributes") or []
    if isinstance(attributes, list):
        for attr in attributes:
            if not isinstance(attr, dict):
                continue
            key = (attr.get("key") or attr.get("key_label") or "").lower()
            value = attr.get("value_label") or attr.get("value")
            if not key or not value:
                continue
            if key in ("item_condition", "condition", "etat"):
                condition = value
                listing_attrs["condition"] = value
            elif key in ("marque", "brand"):
                listing_attrs["brand"] = value
            elif key in ("couleur", "color", "colour"):
                listing_attrs["color"] = value
            elif key in ("taille", "size"):
                listing_attrs["size"] = value
            elif key in ("annee", "year", "annee_modele"):
                listing_attrs["year"] = value
            else:
                listing_attrs.setdefault("attributes_raw", {})[key] = value

    # Images
    image_url = ""
    images = ad.get("images") or {}
    if isinstance(images, dict):
        urls = images.get("urls") or images.get("urls_large") or images.get("small_url") or []
        if isinstance(urls, list) and urls:
            image_url = urls[0] if isinstance(urls[0], str) else ""
        elif isinstance(urls, str):
            image_url = urls
    elif isinstance(images, list) and images:
        first = images[0]
        image_url = first if isinstance(first, str) else (first.get("url") or "" if isinstance(first, dict) else "")

    # Fallback to thumb
    if not image_url:
        thumb = images.get("thumb_url") if isinstance(images, dict) else None
        image_url = thumb or ""

    # URL
    url = ad.get("url") or ""
    if not url and ad_id:
        url = f"https://www.leboncoin.fr/ad/collection/{ad_id}.htm"

    # Location info (useful for EU marketplace context)
    location = ad.get("location") or {}
    city = location.get("city") or "" if isinstance(location, dict) else ""

    return {
        "source": "leboncoin",
        "raw_id": f"leboncoin-{ad_id}",
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


class LeboncoinCaller:
    """Async Leboncoin adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os

        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("LEBONCOIN_ENABLED", "true").lower() == "true"
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
                    "Content-Type": "application/json",
                    "api_key": LEBONCOIN_API_KEY,
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
        """Search Leboncoin for active listings in the Collection category."""
        if not self.configured:
            return []

        try:
            leboncoin_circuit.check()
        except CircuitOpenError:
            logger.warning("Leboncoin circuit open — skipping")
            return []

        try:
            client = await self._client()

            body: Dict[str, Any] = {
                "filters": {
                    "keywords": {"text": query},
                    "category": {"id": LEBONCOIN_COLLECTION_CATEGORY_ID},
                },
                "limit": min(limit, 35),
                "offset": 0,
                "sort_by": "relevance",
            }

            resp = await client.post(LEBONCOIN_API_URL, json=body)

            if resp.status_code == 200:
                data = resp.json()
                ads = data.get("ads") or data.get("results") or data.get("items", [])
                leboncoin_circuit.record_success()
                return [_normalize_ad(ad) for ad in ads[:limit]]

            # 2026-04-23 silent-failure sweep: any non-200 must trip the
            # breaker. Original code special-cased only 429/503 and recorded
            # SUCCESS on all other non-2xx (incl. 401/403/451/5xx) so anti-bot
            # blocks let the worker silently return [] forever.
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                leboncoin_circuit.record_failure()
                logger.warning("Leboncoin API HTTP %d — circuit failure", resp.status_code)
            return []

        except Exception as exc:
            leboncoin_circuit.record_failure()
            logger.warning("Leboncoin search error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Leboncoin does not expose sold/completed listings — returns empty.

        The search() method returns active listings only.  For valuation
        purposes other adapters (eBay sold, Catawiki sold, Mavin) should
        be preferred.
        """
        return []

    async def health_check(self) -> bool:
        """Check if Leboncoin API is reachable."""
        if not self.configured:
            return False
        try:
            client = await self._client()
            body = {
                "filters": {
                    "keywords": {"text": "test"},
                    "category": {"id": LEBONCOIN_COLLECTION_CATEGORY_ID},
                },
                "limit": 1,
                "offset": 0,
                "sort_by": "relevance",
            }
            resp = await client.post(LEBONCOIN_API_URL, json=body)
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
