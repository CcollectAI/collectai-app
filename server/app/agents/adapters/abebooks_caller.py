"""
AbeBooks marketplace adapter for the Marketplace Aggregation Agent.

Uses smart_scrape (Crawl4AI-first with Firecrawl fallback) to scrape
AbeBooks search pages. Parses markdown into MarketHit dicts.

Covers: comic_books, manga (2 categories).

AbeBooks is one of the world's largest online marketplaces for books,
including rare comics, manga, and graphic novels. Owned by Amazon.
No sold data is publicly available.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from app.agents.adapters.firecrawl_caller import (
    _content_hash,
    _extract_image_url,
    _extract_price,
)
from app.agents.adapters.crawl4ai_caller import (
    _split_into_listings,
    _extract_title_from_listing,
    _extract_url_from_listing,
)
from workers.circuit_breaker import abebooks_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

ABEBOOKS_SOURCE_RELIABILITY = 0.80

# sortby=17 = "Lowest Price" — best for price discovery
ABEBOOKS_SEARCH_URL = "https://www.abebooks.com/servlet/SearchResults?kn={query}&sortby=17"

SUPPORTED_CATEGORIES = frozenset([
    "comic_books",
    "manga",
])


class AbeBooksCaller:
    """Async AbeBooks adapter using smart_scrape for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("ABEBOOKS_ENABLED", "true").lower() == "true"
        )

    @property
    def configured(self) -> bool:
        return self._enabled

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search AbeBooks for book/comic/manga listings via smart_scrape."""
        if not self.configured:
            logger.debug("[AbeBooksCaller] Not configured")
            return []

        try:
            abebooks_circuit.check()
        except CircuitOpenError:
            logger.warning("[AbeBooksCaller] circuit open — skipping search")
            return []

        from app.lib.smart_scrape import smart_scrape

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        url = ABEBOOKS_SEARCH_URL.replace("{query}", quote_plus(query))

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[AbeBooksCaller] No markdown returned for search")
                return []

            abebooks_circuit.record_success()
            return self._parse_listings(
                result["markdown"], url, rates, limit,
            )

        except Exception:
            abebooks_circuit.record_failure()
            logger.error("[AbeBooksCaller] search failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        AbeBooks does not expose sold/completed order history publicly.
        Returns an empty list.
        """
        return []

    def _parse_listings(
        self,
        markdown: str,
        fallback_url: str,
        rates: Any,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Parse scraped markdown into MarketHit dicts."""
        listings = _split_into_listings(markdown)
        hits: List[Dict[str, Any]] = []

        for listing_text in listings:
            if len(hits) >= limit:
                break

            title = _extract_title_from_listing(listing_text)
            if not title:
                continue

            listing_url = _extract_url_from_listing(listing_text) or fallback_url
            # Ensure AbeBooks relative URLs are made absolute
            if listing_url.startswith("/"):
                listing_url = f"https://www.abebooks.com{listing_url}"

            price_text = f"{title} {listing_text[:500]}"
            price, currency, source_price, source_currency = _extract_price(
                price_text, rates=rates,
            )

            image_url = _extract_image_url(listing_text)

            hit: Dict[str, Any] = {
                "source": "abebooks",
                "raw_id": _content_hash("abebooks", listing_url),
                "title": title[:500],
                "price": price,
                "currency": currency,
                "source_price": source_price,
                "source_currency": source_currency,
                "sold_at": None,
                "url": listing_url,
                "condition": None,
                "image_url": image_url,
                "is_sold": False,
                "content_hash": _content_hash("abebooks", listing_url),
            }

            if hit["price"] is not None:
                hits.append(hit)

        return hits

    async def health_check(self) -> bool:
        """Check if AbeBooks is reachable via smart_scrape."""
        if not self.configured:
            return False
        try:
            from app.lib.smart_scrape import smart_scrape
            result = await smart_scrape("https://www.abebooks.com")
            return result is not None
        except Exception:
            return False

    async def close(self) -> None:
        """No persistent resources to close."""
        pass
