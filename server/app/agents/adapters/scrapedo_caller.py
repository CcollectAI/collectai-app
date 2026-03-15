"""
Scrape.do marketplace adapter for the Marketplace Aggregation Agent.

Uses Scrape.do to scrape marketplace search pages on sites that lack
dedicated APIs. Similar to Crawl4AI but leverages Scrape.do's managed
proxy infrastructure with 98% success rate and anti-bot bypass.

Constructs search URLs for each target site (e.g.,
``ebay.com/sch/i.html?_nkw={query}``) and scrapes the result pages.

Maps scraped results to the same MarketHit dict format as ebay_caller,
tcgplayer_caller, firecrawl_caller, and crawl4ai_caller.

Env vars:
    SCRAPEDO_API_KEY  - Scrape.do API token
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

# Reuse helpers from firecrawl_caller and crawl4ai_caller — no duplication
from app.agents.adapters.firecrawl_caller import (
    CATEGORY_SITE_TARGETS,
    _content_hash,
    _extract_image_url,
    _extract_price,
)
from app.agents.adapters.crawl4ai_caller import (
    SITE_SEARCH_TEMPLATES,
    EBAY_SOLD_SUFFIX,
    _split_into_listings,
    _extract_title_from_listing,
    _extract_url_from_listing,
)
from workers.circuit_breaker import scrapedo_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# Provenance score: higher than Crawl4AI (0.60) due to Scrape.do's 98%
# success rate and managed anti-bot bypass, but below direct APIs
SCRAPEDO_SOURCE_RELIABILITY = 0.70
SCRAPEDO_SOLD_SOURCE_RELIABILITY = 0.75


# ---------------------------------------------------------------------------
# HTML to pseudo-markdown conversion
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_LINK_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _html_to_markdown(html: str) -> str:
    """Convert raw HTML to a simplified markdown-like text.

    This is a lightweight conversion — just enough to let the
    shared listing-splitting and price-extraction helpers work.
    """
    if not html:
        return ""

    text = html

    # Convert images to markdown
    text = _IMG_RE.sub(r"![](\1)", text)

    # Convert links to markdown
    text = _LINK_RE.sub(r"[\2](\1)", text)

    # Replace block elements with newlines
    for tag in ("</div>", "</p>", "</li>", "</tr>", "</h1>", "</h2>", "</h3>", "<br>", "<br/>", "<br />"):
        text = text.replace(tag, "\n")

    # Strip remaining HTML tags
    text = _TAG_RE.sub(" ", text)

    # Collapse whitespace (but preserve newlines)
    lines = text.split("\n")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in lines]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ScrapedoCaller:
    """Async Scrape.do web scraper for the marketplace aggregation agent."""

    def __init__(self) -> None:
        pass

    @property
    def configured(self) -> bool:
        try:
            from app.lib.scrapedo_client import configured as sd_configured
            return sd_configured()
        except ImportError:
            return False

    def _build_search_url(self, query: str, site: str, sold: bool = False) -> str:
        """Construct a search URL for the given site."""
        encoded = quote_plus(query)
        template = SITE_SEARCH_TEMPLATES.get(site)

        if template:
            url = template.replace("{query}", encoded)
        else:
            # Fallback: Google site-restricted search
            url = f"https://www.google.com/search?q={encoded}+site%3A{quote_plus(site)}"

        # For eBay sold comps, append sold filters
        if sold and "ebay" in site:
            url += EBAY_SOLD_SUFFIX

        return url

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region_sites: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for marketplace listings by scraping site search pages via Scrape.do.

        Constructs search URLs for category-specific sites and scrapes them.
        Returns normalized MarketHit dicts.
        """
        if not self.configured:
            logger.debug("[ScrapedoCaller] Not configured")
            return []

        try:
            scrapedo_circuit.check()
        except CircuitOpenError:
            logger.warning("[ScrapedoCaller] circuit open — skipping search")
            return []

        from app.lib.scrapedo_client import scrape_url

        # Fetch live FX rates
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        # Determine target sites
        sites = region_sites
        if not sites and category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]
        if not sites:
            sites = ["ebay.com"]

        all_hits: List[Dict[str, Any]] = []
        failures = 0

        for site in sites[:3]:  # cap at 3 sites per search
            url = self._build_search_url(query, site)

            try:
                html = await scrape_url(url)
                if not html:
                    continue

                markdown = _html_to_markdown(html)
                if not markdown:
                    continue

                listings = _split_into_listings(markdown)
                for listing_text in listings:
                    if len(all_hits) >= limit:
                        break

                    title = _extract_title_from_listing(listing_text)
                    if not title:
                        continue

                    listing_url = _extract_url_from_listing(listing_text) or url
                    price_text = f"{title} {listing_text[:500]}"
                    price, currency, source_price, source_currency = _extract_price(
                        price_text, rates=rates,
                    )

                    image_url = _extract_image_url(listing_text)

                    sold_keywords = ["sold", "completed", "ended", "past sale"]
                    is_sold = any(kw in listing_text.lower() for kw in sold_keywords)

                    hit: Dict[str, Any] = {
                        "source": "scrapedo",
                        "raw_id": _content_hash("scrapedo", listing_url),
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
                        "content_hash": _content_hash("scrapedo", listing_url),
                    }

                    if hit["price"] is not None:
                        all_hits.append(hit)

            except Exception:
                failures += 1
                logger.error("[ScrapedoCaller] search failed for %s", site, exc_info=True)
                continue

        return all_hits[:limit]

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region_sites: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for sold/completed listings via Scrape.do.

        For eBay: appends sold filters. For others: appends "sold" to query.
        """
        if not self.configured:
            return []

        try:
            scrapedo_circuit.check()
        except CircuitOpenError:
            logger.warning("[ScrapedoCaller] circuit open — skipping sold_comps")
            return []

        from app.lib.scrapedo_client import scrape_url

        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        sites = region_sites
        if not sites and category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]
        if not sites:
            sites = ["ebay.com"]

        all_hits: List[Dict[str, Any]] = []

        for site in sites[:3]:
            # eBay: use sold filter params. Others: append "sold" to query.
            if "ebay" in site:
                sold_query = query
                url = self._build_search_url(sold_query, site, sold=True)
            else:
                sold_query = f"{query} sold"
                url = self._build_search_url(sold_query, site)

            try:
                html = await scrape_url(url)
                if not html:
                    continue

                markdown = _html_to_markdown(html)
                if not markdown:
                    continue

                listings = _split_into_listings(markdown)
                for listing_text in listings:
                    if len(all_hits) >= limit:
                        break

                    title = _extract_title_from_listing(listing_text)
                    if not title:
                        continue

                    listing_url = _extract_url_from_listing(listing_text) or url
                    price_text = f"{title} {listing_text[:500]}"
                    price, currency, source_price, source_currency = _extract_price(
                        price_text, rates=rates,
                    )

                    image_url = _extract_image_url(listing_text)

                    hit: Dict[str, Any] = {
                        "source": "scrapedo",
                        "raw_id": _content_hash("scrapedo", listing_url),
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
                        "content_hash": _content_hash("scrapedo", listing_url),
                    }

                    if hit["price"] is not None:
                        all_hits.append(hit)

            except Exception:
                logger.error("[ScrapedoCaller] sold_comps failed for %s", site, exc_info=True)
                continue

        return all_hits[:limit]

    async def health_check(self) -> bool:
        """Check if Scrape.do is configured and can scrape a simple page."""
        if not self.configured:
            return False
        try:
            from app.lib.scrapedo_client import scrape_url
            result = await scrape_url("https://www.example.com")
            return result is not None
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        try:
            from app.lib.scrapedo_client import close as sd_close
            await sd_close()
        except ImportError:
            pass
