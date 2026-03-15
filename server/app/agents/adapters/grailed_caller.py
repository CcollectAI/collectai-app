"""
Grailed marketplace adapter for the Marketplace Aggregation Agent.

Grailed has no public API, so this adapter uses ``smart_scrape`` (Crawl4AI-first
with Firecrawl fallback) to scrape Grailed search and sold pages.

Constructs search/sold URLs directly on grailed.com and parses the returned
markdown into normalised MarketHit dicts.

Category routing: sneakers, hot_toys, funko, designer_toys, pop_fandom.
"""

from __future__ import annotations

import logging
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
from workers.circuit_breaker import grailed_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# Provenance scores — on par with Scrape.do (scrape-based, no official API)
GRAILED_SOURCE_RELIABILITY = 0.70
GRAILED_SOLD_SOURCE_RELIABILITY = 0.75

# Categories that Grailed covers well
GRAILED_CATEGORIES = frozenset({
    "sneakers",
    "hot_toys",
    "funko",
    "designer_toys",
    "pop_fandom",
})

# Grailed-specific URL for extracting listing links
_GRAILED_URL_RE = re.compile(r"https?://(?:www\.)?grailed\.com/listings/\d+[^\s)\"]*")


def _extract_grailed_url(text: str) -> Optional[str]:
    """Extract a Grailed listing URL from a text block, falling back to generic."""
    m = _GRAILED_URL_RE.search(text)
    if m:
        return m.group(0)
    return _extract_url_from_listing(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class GrailedCaller:
    """Async Grailed scraper for the marketplace aggregation agent."""

    def __init__(self) -> None:
        pass

    @property
    def configured(self) -> bool:
        """Grailed uses smart_scrape (Crawl4AI / Firecrawl) — always available
        if at least one scraper is configured."""
        try:
            from app.lib import crawl4ai_client, firecrawl_client
            return crawl4ai_client.configured() or firecrawl_client.configured()
        except ImportError:
            return False

    def _build_search_url(self, query: str) -> str:
        encoded = quote_plus(query)
        return f"https://www.grailed.com/shop?query={encoded}&sort=new"

    def _build_sold_url(self, query: str) -> str:
        encoded = quote_plus(query)
        return f"https://www.grailed.com/sold?query={encoded}"

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for active Grailed listings via smart_scrape."""
        if not self.configured:
            logger.debug("[GrailedCaller] Not configured")
            return []

        try:
            grailed_circuit.check()
        except CircuitOpenError:
            logger.warning("[GrailedCaller] circuit open — skipping search")
            return []

        from app.lib.smart_scrape import smart_scrape

        # Fetch live FX rates
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        url = self._build_search_url(query)

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[GrailedCaller] empty result for %s", url)
                return []

            grailed_circuit.record_success()

            all_hits: List[Dict[str, Any]] = []
            listings = _split_into_listings(result["markdown"])

            for listing_text in listings:
                if len(all_hits) >= limit:
                    break

                title = _extract_title_from_listing(listing_text)
                if not title:
                    continue

                listing_url = _extract_grailed_url(listing_text) or url
                price_text = f"{title} {listing_text[:500]}"
                price, currency, source_price, source_currency = _extract_price(
                    price_text, rates=rates,
                )

                image_url = _extract_image_url(listing_text)

                sold_keywords = ["sold", "completed", "ended", "past sale"]
                is_sold = any(kw in listing_text.lower() for kw in sold_keywords)

                hit: Dict[str, Any] = {
                    "source": "grailed",
                    "raw_id": _content_hash("grailed", listing_url),
                    "title": title[:500],
                    "price": price,
                    "currency": currency,
                    "source_price": source_price,
                    "source_currency": source_currency,
                    "sold_at": None,
                    "url": listing_url,
                    "condition": None,
                    "image_url": image_url,
                    "is_sold": is_sold,
                    "content_hash": _content_hash("grailed", listing_url),
                }

                if hit["price"] is not None:
                    all_hits.append(hit)

            return all_hits[:limit]

        except Exception:
            grailed_circuit.record_failure()
            logger.error("[GrailedCaller] search failed for %s", url, exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for sold Grailed listings via smart_scrape."""
        if not self.configured:
            return []

        try:
            grailed_circuit.check()
        except CircuitOpenError:
            logger.warning("[GrailedCaller] circuit open — skipping sold_comps")
            return []

        from app.lib.smart_scrape import smart_scrape

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        url = self._build_sold_url(query)

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[GrailedCaller] empty sold result for %s", url)
                return []

            grailed_circuit.record_success()

            all_hits: List[Dict[str, Any]] = []
            listings = _split_into_listings(result["markdown"])

            for listing_text in listings:
                if len(all_hits) >= limit:
                    break

                title = _extract_title_from_listing(listing_text)
                if not title:
                    continue

                listing_url = _extract_grailed_url(listing_text) or url
                price_text = f"{title} {listing_text[:500]}"
                price, currency, source_price, source_currency = _extract_price(
                    price_text, rates=rates,
                )

                image_url = _extract_image_url(listing_text)

                hit: Dict[str, Any] = {
                    "source": "grailed",
                    "raw_id": _content_hash("grailed", listing_url),
                    "title": title[:500],
                    "price": price,
                    "currency": currency,
                    "source_price": source_price,
                    "source_currency": source_currency,
                    "sold_at": None,
                    "url": listing_url,
                    "condition": None,
                    "image_url": image_url,
                    "is_sold": True,
                    "content_hash": _content_hash("grailed", listing_url),
                }

                if hit["price"] is not None:
                    all_hits.append(hit)

            return all_hits[:limit]

        except Exception:
            grailed_circuit.record_failure()
            logger.error("[GrailedCaller] sold_comps failed for %s", url, exc_info=True)
            return []

    async def health_check(self) -> bool:
        """Check if Grailed scraping is available."""
        if not self.configured:
            return False
        try:
            from app.lib.smart_scrape import smart_scrape
            result = await smart_scrape("https://www.grailed.com")
            return result is not None
        except Exception:
            return False

    async def close(self) -> None:
        """No persistent resources to close."""
        pass
