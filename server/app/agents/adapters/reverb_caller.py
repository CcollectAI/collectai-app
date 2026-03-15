"""
Reverb marketplace adapter for the Marketplace Aggregation Agent.

Uses smart_scrape (Crawl4AI-first with Firecrawl fallback) to scrape
Reverb search and sold-listing pages. Parses markdown into MarketHit dicts.

Covers: vinyl_records, anime_ost_vinyl (2 categories).

Reverb is the world's largest online marketplace for musical instruments
and gear, with a large vinyl records section and transparent sold pricing.
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
from workers.circuit_breaker import reverb_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

REVERB_SOURCE_RELIABILITY = 0.80
REVERB_SOLD_SOURCE_RELIABILITY = 0.85

REVERB_SEARCH_URL = "https://reverb.com/marketplace?query={query}&sort=price%7Casc"
REVERB_SOLD_URL = "https://reverb.com/marketplace?query={query}&sort=date%7Cdesc&sold=true"

SUPPORTED_CATEGORIES = frozenset([
    "vinyl_records",
    "anime_ost_vinyl",
])


class ReverbCaller:
    """Async Reverb adapter using smart_scrape for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("REVERB_ENABLED", "true").lower() == "true"
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
        """Search Reverb for active listings via smart_scrape."""
        if not self.configured:
            logger.debug("[ReverbCaller] Not configured")
            return []

        try:
            reverb_circuit.check()
        except CircuitOpenError:
            logger.warning("[ReverbCaller] circuit open — skipping search")
            return []

        from app.lib.smart_scrape import smart_scrape

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        url = REVERB_SEARCH_URL.replace("{query}", quote_plus(query))

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[ReverbCaller] No markdown returned for search")
                return []

            reverb_circuit.record_success()
            return self._parse_listings(
                result["markdown"], url, rates, limit, is_sold=False,
            )

        except Exception:
            reverb_circuit.record_failure()
            logger.error("[ReverbCaller] search failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search Reverb for sold listings via smart_scrape."""
        if not self.configured:
            return []

        try:
            reverb_circuit.check()
        except CircuitOpenError:
            logger.warning("[ReverbCaller] circuit open — skipping sold_comps")
            return []

        from app.lib.smart_scrape import smart_scrape

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        url = REVERB_SOLD_URL.replace("{query}", quote_plus(query))

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[ReverbCaller] No markdown returned for sold_comps")
                return []

            reverb_circuit.record_success()
            return self._parse_listings(
                result["markdown"], url, rates, limit, is_sold=True,
            )

        except Exception:
            reverb_circuit.record_failure()
            logger.error("[ReverbCaller] sold_comps failed", exc_info=True)
            return []

    def _parse_listings(
        self,
        markdown: str,
        fallback_url: str,
        rates: Any,
        limit: int,
        is_sold: bool,
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
            # Ensure Reverb relative URLs are made absolute
            if listing_url.startswith("/"):
                listing_url = f"https://reverb.com{listing_url}"

            price_text = f"{title} {listing_text[:500]}"
            price, currency, source_price, source_currency = _extract_price(
                price_text, rates=rates,
            )

            image_url = _extract_image_url(listing_text)

            # Detect sold keywords if not explicitly sold mode
            if not is_sold:
                sold_keywords = ["sold", "completed", "ended", "past sale"]
                is_sold_item = any(kw in listing_text.lower() for kw in sold_keywords)
            else:
                is_sold_item = True

            hit: Dict[str, Any] = {
                "source": "reverb",
                "raw_id": _content_hash("reverb", listing_url),
                "title": title[:500],
                "price": price,
                "currency": currency,
                "source_price": source_price,
                "source_currency": source_currency,
                "sold_at": None,
                "url": listing_url,
                "condition": None,
                "image_url": image_url,
                "is_sold": is_sold_item,
                "content_hash": _content_hash("reverb", listing_url),
            }

            if hit["price"] is not None:
                hits.append(hit)

        return hits

    async def health_check(self) -> bool:
        """Check if Reverb is reachable via smart_scrape."""
        if not self.configured:
            return False
        try:
            from app.lib.smart_scrape import smart_scrape
            result = await smart_scrape("https://reverb.com")
            return result is not None
        except Exception:
            return False

    async def close(self) -> None:
        """No persistent resources to close."""
        pass
