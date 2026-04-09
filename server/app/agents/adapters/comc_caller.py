"""
COMC (Check Out My Cards) marketplace adapter for the Marketplace Aggregation Agent.

Uses smart_scrape (Crawl4AI-first with Firecrawl fallback) to scrape
COMC search and sold-listing pages. Parses markdown into MarketHit dicts.

Covers: sportscards, pokemon, mtg, yugioh (4 categories).

COMC is one of the largest consignment marketplaces for trading cards,
with transparent pricing and detailed card condition grading.
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
from workers.circuit_breaker import comc_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

COMC_SOURCE_RELIABILITY = 0.80
COMC_SOLD_SOURCE_RELIABILITY = 0.85

COMC_SEARCH_URL = "https://www.comc.com/Cards?text={query}&sort=BestMatch"
COMC_SOLD_URL = "https://www.comc.com/Cards?text={query}&sort=RecentlySold"

SUPPORTED_CATEGORIES = frozenset([
    "sportscards",
    "pokemon",
    "mtg",
    "yugioh",
])

# Stop-words that shouldn't count as "significant" for relevance filtering
_STOP_WORDS = frozenset([
    "the", "and", "for", "with", "card", "cards", "set", "edition",
    "vmax", "vstar", "ex", "gx", "v", "tg", "promo",  # generic TCG suffixes
])


def _filter_by_query_relevance(hits: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Drop hits whose title doesn't contain at least one significant word from the query.

    R47 — defensive filter for COMC. The scraper can return irrelevant results
    when JS rendering fails or the site falls back to a default page. We keep
    a hit only if its title contains at least one ≥3-char non-stop-word from
    the original query.
    """
    significant = {
        w.lower()
        for w in query.split()
        if len(w) >= 3 and w.lower() not in _STOP_WORDS
    }
    if not significant:
        return hits  # query was all stop-words — don't filter

    filtered = []
    dropped = 0
    for hit in hits:
        title = (hit.get("title") or "").lower()
        if any(w in title for w in significant):
            filtered.append(hit)
        else:
            dropped += 1
    if dropped:
        logger.debug(
            "[COMCCaller] relevance filter dropped %d/%d hits (query=%s)",
            dropped, len(hits), query,
        )
    return filtered


class COMCCaller:
    """Async COMC adapter using smart_scrape for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("COMC_ENABLED", "true").lower() == "true"
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
        """Search COMC for active card listings via smart_scrape."""
        if not self.configured:
            logger.debug("[COMCCaller] Not configured")
            return []

        # R47 — Category gate. COMC only carries trading cards (sportscards,
        # pokemon, mtg, yugioh). Without this check, the previous version
        # silently accepted any category and returned irrelevant results
        # (e.g. NHL hockey cards for a Pokemon query).
        if category and category not in SUPPORTED_CATEGORIES:
            logger.debug("[COMCCaller] category %s not supported — skipping", category)
            return []

        try:
            comc_circuit.check()
        except CircuitOpenError:
            logger.warning("[COMCCaller] circuit open — skipping search")
            return []

        from app.lib.smart_scrape import smart_scrape

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        # R47 — Bias the text search by prefixing the category name.
        # COMC's text= param is fuzzy and doesn't reliably narrow results
        # without an explicit term. "Pokemon Charizard VMAX" beats just
        # "Charizard VMAX" for relevance.
        biased_query = f"{category} {query}" if category else query
        url = COMC_SEARCH_URL.replace("{query}", quote_plus(biased_query))

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[COMCCaller] No markdown returned for search")
                return []

            comc_circuit.record_success()
            hits = self._parse_listings(
                result["markdown"], url, rates, limit, is_sold=False,
            )
            # R47 — Post-parse relevance filter. Drop listings whose title
            # doesn't contain any significant word (≥3 chars) from the
            # original query. Catches the case where COMC's scraper falls
            # back to a default page on cache/JS issues.
            return _filter_by_query_relevance(hits, query)

        except Exception:
            comc_circuit.record_failure()
            logger.error("[COMCCaller] search failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search COMC for recently sold card listings via smart_scrape."""
        if not self.configured:
            return []

        # R47 — same category gate as search()
        if category and category not in SUPPORTED_CATEGORIES:
            logger.debug("[COMCCaller] category %s not supported — skipping sold_comps", category)
            return []

        try:
            comc_circuit.check()
        except CircuitOpenError:
            logger.warning("[COMCCaller] circuit open — skipping sold_comps")
            return []

        from app.lib.smart_scrape import smart_scrape

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        biased_query = f"{category} {query}" if category else query
        url = COMC_SOLD_URL.replace("{query}", quote_plus(biased_query))

        try:
            result = await smart_scrape(url)
            if not result or not result.get("markdown"):
                logger.debug("[COMCCaller] No markdown returned for sold_comps")
                return []

            comc_circuit.record_success()
            hits = self._parse_listings(
                result["markdown"], url, rates, limit, is_sold=True,
            )
            return _filter_by_query_relevance(hits, query)

        except Exception:
            comc_circuit.record_failure()
            logger.error("[COMCCaller] sold_comps failed", exc_info=True)
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
            # Ensure COMC relative URLs are made absolute
            if listing_url.startswith("/"):
                listing_url = f"https://www.comc.com{listing_url}"

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
                "source": "comc",
                "raw_id": _content_hash("comc", listing_url),
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
                "content_hash": _content_hash("comc", listing_url),
            }

            if hit["price"] is not None:
                hits.append(hit)

        return hits

    async def health_check(self) -> bool:
        """Check if COMC is reachable via smart_scrape."""
        if not self.configured:
            return False
        try:
            from app.lib.smart_scrape import smart_scrape
            result = await smart_scrape("https://www.comc.com")
            return result is not None
        except Exception:
            return False

    async def close(self) -> None:
        """No persistent resources to close."""
        pass
