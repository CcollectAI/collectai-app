"""
Discogs API caller for the Marketplace Aggregation Agent.

Discogs is the world's largest music database and marketplace. Covers vinyl
records, CDs, cassettes — key for anime_ost_vinyl, anime_soundtrack, and
kpop_merch categories.

API docs: https://www.discogs.com/developers

Env vars:
    DISCOGS_PERSONAL_TOKEN - Personal access token from Discogs settings
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import DISCOGS_PERSONAL_TOKEN as _CFG_TOKEN
from workers.circuit_breaker import discogs_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISCOGS_BASE = "https://api.discogs.com"
USER_AGENT = "CollectAI/1.0 +https://collectai.app"

# Categories that benefit from Discogs data
SUPPORTED_CATEGORIES = [
    "anime_ost_vinyl",
    "anime_soundtrack",
    "kpop_merch",
    "taylor_swift",
    "pop_fandom",
    "bluray_steelbook",
]

DISCOGS_SOURCE_RELIABILITY = 0.80


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_release(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Discogs marketplace listing or search result."""
    # Search results have different shape than marketplace listings
    title = item.get("title", "Unknown")
    thumb = item.get("thumb") or item.get("cover_image") or ""
    year = item.get("year")
    country = item.get("country") or ""
    formats = item.get("format", [])
    format_str = ", ".join(formats) if isinstance(formats, list) else str(formats)

    # Price data from marketplace stats or lowest_price
    community = item.get("community", {})
    stats = item.get("stats", {})
    lowest = item.get("lowest_price")

    return {
        "source": "discogs",
        "raw_id": f"discogs-{item.get('id', '')}",
        "title": title,
        "price": float(lowest) if lowest else 0,
        "currency": "USD",
        "source_price": float(lowest) if lowest else 0,
        "source_currency": "USD",
        "url": item.get("uri", f"https://www.discogs.com/release/{item.get('id', '')}"),
        "condition": None,
        "image_url": thumb,
        "is_sold": False,
        "year": str(year) if year else None,
        "format": format_str,
        "country": country,
        "have": community.get("have"),
        "want": community.get("want"),
    }


def _normalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Discogs marketplace listing."""
    release = listing.get("release", {})
    price_info = listing.get("price", {})
    condition = listing.get("condition") or ""
    sleeve = listing.get("sleeve_condition") or ""

    return {
        "source": "discogs",
        "raw_id": f"discogs-listing-{listing.get('id', '')}",
        "title": release.get("description") or release.get("title", "Unknown"),
        "price": float(price_info.get("value", 0)),
        "currency": price_info.get("currency", "USD"),
        "source_price": float(price_info.get("value", 0)),
        "source_currency": price_info.get("currency", "USD"),
        "url": listing.get("uri", ""),
        "condition": f"Media: {condition}, Sleeve: {sleeve}" if sleeve else condition,
        "image_url": release.get("thumbnail") or "",
        "is_sold": False,
        "ships_from": listing.get("ships_from") or None,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class DiscogsCaller:
    """Async Discogs API caller for the marketplace aggregation agent."""

    def __init__(self, personal_token: Optional[str] = None):
        self.token = personal_token or _CFG_TOKEN
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.token)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": USER_AGENT,
                    "Authorization": f"Discogs token={self.token}",
                },
            )
        return self._http

    async def search(
        self,
        query: str,
        category: str = "anime_ost_vinyl",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search Discogs database for releases matching a query."""
        if not self.configured:
            logger.debug("Discogs not configured — skipping search")
            return []

        try:
            discogs_circuit.check()
        except CircuitOpenError:
            logger.warning("Discogs circuit open — skipping")
            return []

        # Build search params with format hints based on category
        params: Dict[str, str] = {
            "q": query,
            "per_page": str(min(limit, 100)),
            "type": "release",
        }

        # Add format filter based on category
        if category in ("anime_ost_vinyl",):
            params["format"] = "Vinyl"
        elif category in ("anime_soundtrack",):
            params["format"] = "CD"

        try:
            client = await self._client()
            resp = await client.get(f"{DISCOGS_BASE}/database/search", params=params)
            resp.raise_for_status()
            data = resp.json()
            discogs_circuit.record_success()

            results = data.get("results", [])
            return [_normalize_release(r) for r in results[:limit]]

        except Exception as exc:
            discogs_circuit.record_failure()
            logger.warning("Discogs search error: %s", exc)
            return []

    async def marketplace_listings(
        self,
        release_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get active marketplace listings for a specific release."""
        if not self.configured:
            return []

        try:
            discogs_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                f"{DISCOGS_BASE}/marketplace/listings",
                params={
                    "release_id": str(release_id),
                    "per_page": str(min(limit, 50)),
                    "sort": "price",
                    "sort_order": "asc",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            discogs_circuit.record_success()

            listings = data.get("listings", [])
            return [_normalize_listing(l) for l in listings[:limit]]

        except Exception as exc:
            discogs_circuit.record_failure()
            logger.warning("Discogs marketplace error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: str = "anime_ost_vinyl",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Get price statistics from Discogs (lowest_price field from search)."""
        results = await self.search(query, category, limit)
        for r in results:
            r["is_sold"] = True
        return results

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(f"{DISCOGS_BASE}/database/search", params={"q": "test", "per_page": "1"})
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
