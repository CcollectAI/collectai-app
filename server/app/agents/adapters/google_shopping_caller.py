"""
Google Shopping marketplace adapter for the Marketplace Aggregation Agent.

Uses SerpAPI's Google Shopping endpoint to find product listings across
all categories. Google Shopping aggregates prices from many retailers,
making it a useful unrestricted data source.

Maps search results to the same MarketHit dict format as other adapters.

Env vars:
    SERPAPI_API_KEY  - SerpAPI API key
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from workers.circuit_breaker import google_shopping_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# Provenance score: Google Shopping aggregates retailer prices — reliable
# but not as authoritative as direct marketplace APIs (eBay sold, TCGPlayer).
GOOGLE_SHOPPING_SOURCE_RELIABILITY = 0.75


def _content_hash(url: str) -> str:
    """Compute SHA-256 content hash for deduplication."""
    payload = f"google_shopping:{url}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _region_to_gl(region: Optional[str]) -> Optional[str]:
    """Map CollectAI region to Google country code."""
    mapping = {
        "americas": "us",
        "europe": "de",
        "japan": "jp",
        "korea": "kr",
        "other": None,
    }
    return mapping.get(region or "other")


class GoogleShoppingCaller:
    """Async Google Shopping caller for the marketplace aggregation agent."""

    def __init__(self) -> None:
        pass

    @property
    def configured(self) -> bool:
        try:
            from app.lib.google_shopping_client import configured as gs_configured
            return gs_configured()
        except ImportError:
            return False

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search Google Shopping for product listings via SerpAPI.

        Returns normalized MarketHit dicts.
        Google Shopping is unrestricted — works for all categories.
        """
        if not self.configured:
            logger.debug("[GoogleShoppingCaller] Not configured (no SERPAPI_API_KEY)")
            return []

        try:
            google_shopping_circuit.check()
        except CircuitOpenError:
            logger.warning("[GoogleShoppingCaller] circuit open — skipping search")
            return []

        from app.lib.google_shopping_client import search as gs_search

        # Fetch live FX rates for price conversion
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        # Enrich query with category context for better results
        search_query = f"{query} collectible" if category else query
        gl = _region_to_gl(region)

        try:
            results = await gs_search(search_query, num=min(limit, 10), gl=gl)
        except Exception:
            logger.error("[GoogleShoppingCaller] search failed", exc_info=True)
            return []

        hits: List[Dict[str, Any]] = []
        for item in results:
            if len(hits) >= limit:
                break

            title = item.get("title", "")
            if not title:
                continue

            # Extract price — SerpAPI provides extracted_price as a float
            price = item.get("extracted_price")
            if price is None or price <= 0:
                continue

            link = item.get("link", "")
            source_name = item.get("source", "Google Shopping")
            thumbnail = item.get("thumbnail")

            # SerpAPI Google Shopping prices are in the user's local currency
            # (determined by gl param). Convert to EUR using FX rates.
            source_currency = "USD"  # Default assumption for Google Shopping
            price_eur = price
            if rates:
                from app.config import USD_TO_EUR
                rate = rates.get("USD", USD_TO_EUR)
                price_eur = round(price * rate, 2)
            else:
                from app.config import USD_TO_EUR
                price_eur = round(price * USD_TO_EUR, 2)

            hit: Dict[str, Any] = {
                "source": "google_shopping",
                "raw_id": _content_hash(link or f"{title}:{price}"),
                "title": title[:500],
                "price": price_eur,
                "currency": "EUR",
                "source_price": price,
                "source_currency": source_currency,
                "sold_at": None,
                "url": link,
                "condition": None,
                "image_url": thumbnail,
                "is_sold": False,
                "content_hash": _content_hash(link or f"{title}:{price}"),
                "seller": source_name,
            }
            hits.append(hit)

        return hits

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Google Shopping does not provide sold/completed listing data.

        Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        """Check if SerpAPI Google Shopping is reachable."""
        if not self.configured:
            return False
        try:
            from app.lib.google_shopping_client import search as gs_search
            results = await gs_search("collectible", num=1)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        try:
            from app.lib.google_shopping_client import close as gs_close
            await gs_close()
        except ImportError:
            pass
