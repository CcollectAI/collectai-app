"""
Crawl4AI marketplace adapter for the Marketplace Aggregation Agent.

Uses Crawl4AI to directly crawl marketplace search pages on sites that lack
dedicated APIs. Unlike Firecrawl (which has /search), Crawl4AI crawls URLs
directly — so this adapter constructs search URLs for each target site
(e.g., ``ebay.com/sch/i.html?_nkw={query}``) and scrapes the result pages.

Maps scraped results to the same MarketHit dict format as ebay_caller,
tcgplayer_caller, and firecrawl_caller.

Env vars:
    CRAWL4AI_ENABLED  - "true" to enable
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

# Reuse helpers from firecrawl_caller — no duplication
from app.agents.adapters.firecrawl_caller import (
    CATEGORY_SITE_TARGETS,
    _content_hash,
    _extract_image_url,
    _extract_price,
)
from workers.circuit_breaker import crawl4ai_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# Provenance score: slightly below Firecrawl (0.65) since we parse raw page markdown
CRAWL4AI_SOURCE_RELIABILITY = 0.60
CRAWL4AI_SOLD_SOURCE_RELIABILITY = 0.65

# ---------------------------------------------------------------------------
# Search URL templates per site
# ---------------------------------------------------------------------------
# {query} is replaced with URL-encoded search terms.
# Sites not listed here get a generic Google site-search fallback.

SITE_SEARCH_TEMPLATES: Dict[str, str] = {
    # Major marketplaces
    "ebay.com": "https://www.ebay.com/sch/i.html?_nkw={query}",
    "ebay.de": "https://www.ebay.de/sch/i.html?_nkw={query}",
    "ebay.co.uk": "https://www.ebay.co.uk/sch/i.html?_nkw={query}",
    "mercari.com": "https://www.mercari.com/search/?keyword={query}",
    "mercari.com/jp": "https://jp.mercari.com/search?keyword={query}",
    "stockx.com": "https://stockx.com/search?s={query}",
    # TCG / Collectible cards
    "tcgplayer.com": "https://www.tcgplayer.com/search/all/product?q={query}",
    "cardmarket.com": "https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={query}",
    "pricecharting.com": "https://www.pricecharting.com/search-products?q={query}",
    "130point.com": "https://130point.com/sales/?search={query}",
    # Figures / Anime
    "myfigurecollection.net": "https://myfigurecollection.net/browse.v4.php?keywords={query}",
    "amiami.com": "https://www.amiami.com/eng/search/list/?s_keywords={query}",
    "solarisjapan.com": "https://solarisjapan.com/search?q={query}",
    "sideshow.com": "https://www.sideshow.com/search?keywords={query}",
    "suruga-ya.jp": "https://www.suruga-ya.jp/search?category=&search_word={query}",
    # Building / Models
    "bricklink.com": "https://www.bricklink.com/v2/search.page?q={query}",
    "brickset.com": "https://brickset.com/sets?query={query}",
    "scalemates.com": "https://www.scalemates.com/search.php?q={query}",
    "hlj.com": "https://www.hlj.com/search/?q={query}",
    "gundamplanet.com": "https://www.gundamplanet.com/search?q={query}",
    "thetrolltrader.com": "https://thetrolltrader.com/search?q={query}",
    # Music / K-pop
    "ktown4u.com": "https://www.ktown4u.com/search?goodsTextSearch={query}",
    "discogs.com": "https://www.discogs.com/search/?q={query}&type=all",
    "vgmdb.net": "https://vgmdb.net/search?q={query}",
    # Other
    "hobbydb.com": "https://www.hobbydb.com/marketplaces/hobbydb/catalog_items?q={query}",
    "whatnot.com": "https://www.whatnot.com/search?query={query}",
    "buyee.jp": "https://buyee.jp/item/search/query/{query}",
    "comc.com": "https://www.comc.com/Cards?key={query}",
    # JP auctions
    "yahoo.co.jp/auctions": "https://auctions.yahoo.co.jp/search/search?p={query}",
    # ─── (additions below) ───
    # ─── Added 2026-04-25: dead specialty APIs replaced with public-page scraping
    # so thin categories (watches, whiskey, lego, scale models) keep getting hits
    # via Crawl4AI without needing API access we don't have.
    "chrono24.com": "https://www.chrono24.com/search/index.htm?query={query}",
    "whiskyauctioneer.com": "https://www.whiskyauctioneer.com/search?q={query}",
    "masterofmalt.com": "https://www.masterofmalt.com/search/?searchTerm={query}",
    "brickeconomy.com": "https://www.brickeconomy.com/search?query={query}",
    "bezel.com": "https://getbezel.com/search?q={query}",
    "popmart.com": "https://www.popmart.com/search?keyword={query}",
    "mavin.io": "https://mavin.io/search?q={query}",
    "etsy.com": "https://www.etsy.com/search?q={query}",
    "leboncoin.fr": "https://www.leboncoin.fr/recherche?text={query}",
    "marktplaats.nl": "https://www.marktplaats.nl/q/{query}/",
    "kleinanzeigen.de": "https://www.kleinanzeigen.de/s-{query}/k0",
    "wallapop.com": "https://es.wallapop.com/app/search?keywords={query}",
}

# eBay sold-listing URL suffix
EBAY_SOLD_SUFFIX = "&LH_Complete=1&LH_Sold=1"

# CSS wait selectors for JS-heavy sites (Playwright will wait before extracting)
SITE_WAIT_SELECTORS: Dict[str, str] = {
    "stockx.com": "[data-testid='product-tile']",
    "mercari.com": "[data-testid='SearchResults']",
    "whatnot.com": "[class*='listing']",
    "weverse.io": "[class*='feed']",
}


# ---------------------------------------------------------------------------
# Listing splitting from raw markdown
# ---------------------------------------------------------------------------

# Heuristic split: two or more blank lines, or horizontal rules, or numbered lists
_LISTING_SPLIT_RE = re.compile(r"\n{3,}|^-{3,}$|^\*{3,}$|^#{1,3}\s", re.MULTILINE)


def _split_into_listings(markdown: str, max_listings: int = 30) -> List[str]:
    """Split a search-results page markdown into individual listing candidates."""
    parts = _LISTING_SPLIT_RE.split(markdown)
    # Filter tiny fragments and limit
    return [p.strip() for p in parts if len(p.strip()) > 30][:max_listings]


def _extract_title_from_listing(text: str) -> Optional[str]:
    """Extract a title from a listing text block."""
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip().lstrip("#").strip()
        if 10 <= len(line) <= 300:
            # Strip markdown link syntax
            cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
            if cleaned:
                return cleaned[:300]
    return None


_ATTR_PATTERNS = [
    # (regex, canonical_key)
    (r"(?:condition|état|zustand|conditie)\s*[:\-—]\s*([A-Za-z0-9 ]{2,32})", "condition"),
    (r"(?:brand|marke|marca|marque)\s*[:\-—]\s*([A-Za-z0-9 .&'\-]{2,40})", "brand"),
    (r"(?:size|größe|talla|taille)\s*[:\-—]\s*([A-Za-z0-9 .]{1,16})", "size"),
    (r"(?:color|colour|couleur|farbe|colore)\s*[:\-—]\s*([A-Za-z ]{3,24})", "color"),
    (r"(?:year|année|jahr|año)\s*[:\-—]\s*(\d{4})", "year"),
    (r"(?:material|matière|materiale|matériau)\s*[:\-—]\s*([A-Za-z ]{3,32})", "material"),
    # Card-grading: "PSA 10", "BGS 9.5", "CGC 8"
    (r"\b(PSA|BGS|CGC|SGC)\s*(\d{1,2}(?:\.\d)?)\b", "grade"),
    # Foil markers — common TCG/collectible printing axis
    (r"\b(holofoil|reverse holo|foil|normal printing)\b", "printing"),
]


def _extract_attrs_from_text(text: str) -> Dict[str, Any]:
    """Best-effort regex extraction of common per-listing attribute fields
    from raw listing markdown. Cheap; per-site precision is low; relies on
    attribute_normalizer downstream to drop garbage values. Even 20%
    coverage is a win because crawl4ai currently writes 0% attrs."""
    attrs: Dict[str, Any] = {}
    if not text:
        return attrs
    snippet = text[:2000]  # cap regex scope — listings markdown is verbose
    for pattern, key in _ATTR_PATTERNS:
        m = re.search(pattern, snippet, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if key == "grade":
                # Two-group pattern: grader + score → "PSA 10"
                value = f"{m.group(1).upper()} {m.group(2)}"
            if value and key not in attrs:
                attrs[key] = value
    return attrs


def _extract_url_from_listing(text: str) -> Optional[str]:
    """Extract the first URL from a listing text block."""
    m = re.search(r"\(?(https?://[^\s)]+)", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Crawl4AICaller:
    """Async Crawl4AI web crawler for the marketplace aggregation agent."""

    def __init__(self) -> None:
        pass

    @property
    def configured(self) -> bool:
        try:
            from app.lib.crawl4ai_client import configured as c4_configured
            return c4_configured()
        except ImportError:
            return False

    def _build_search_url(self, query: str, site: str, sold: bool = False) -> str:
        """Construct a search URL for the given site."""
        encoded = quote_plus(query)
        template = SITE_SEARCH_TEMPLATES.get(site)

        if template:
            url = template.replace("{query}", encoded)
        else:
            # Fallback: DuckDuckGo HTML — Google aggressively blocks scrapers
            # without an API key; DuckDuckGo's /html/ endpoint is scrape-friendly.
            # site: operator narrows to the target domain so we get its listings,
            # not generic web results.
            url = f"https://html.duckduckgo.com/html/?q={encoded}+site%3A{quote_plus(site)}"

        # For eBay sold comps, append sold filters
        if sold and "ebay" in site:
            url += EBAY_SOLD_SUFFIX

        return url

    def _get_wait_selector(self, site: str) -> Optional[str]:
        """Return a wait_for CSS selector if the site is JS-heavy."""
        return SITE_WAIT_SELECTORS.get(site)

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region_sites: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for marketplace listings by crawling site search pages.

        Constructs search URLs for category-specific sites and scrapes them.
        Returns normalized MarketHit dicts.
        """
        if not self.configured:
            logger.debug("[Crawl4AICaller] Not configured")
            return []

        try:
            crawl4ai_circuit.check()
        except CircuitOpenError:
            logger.warning("[Crawl4AICaller] circuit open — skipping search")
            return []

        from app.lib.crawl4ai_client import scrape_url

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
            wait_for = self._get_wait_selector(site)

            try:
                result = await scrape_url(url, wait_for=wait_for)
                if not result or not result.get("markdown"):
                    continue

                crawl4ai_circuit.record_success()

                listings = _split_into_listings(result["markdown"])
                for listing_text in listings:
                    if len(all_hits) >= limit:
                        break

                    title = _extract_title_from_listing(listing_text)
                    if not title:
                        continue

                    listing_url = _extract_url_from_listing(listing_text) or url
                    price_text = f"{title} {listing_text[:500]}"
                    price, currency, source_price, source_currency = _extract_price(price_text, rates=rates)

                    image_url = _extract_image_url(listing_text)

                    sold_keywords = ["sold", "completed", "ended", "past sale"]
                    is_sold = any(kw in listing_text.lower() for kw in sold_keywords)

                    hit: Dict[str, Any] = {
                        "source": "crawl4ai",
                        "raw_id": _content_hash("crawl4ai", listing_url),
                        "title": title[:500],
                        "price": price,
                        "currency": currency,
                        "source_price": source_price,
                        "source_currency": source_currency,
                        "attributes": _extract_attrs_from_text(listing_text),
                        "sold_at": None,
                        "url": listing_url,
                        "condition": None,
                        "image_url": image_url,
                        "is_sold": is_sold,
                        "content_hash": _content_hash("crawl4ai", listing_url),
                    }

                    if hit["price"] is not None:
                        all_hits.append(hit)

            except Exception:
                failures += 1
                crawl4ai_circuit.record_failure()
                logger.error("[Crawl4AICaller] search failed for %s", site, exc_info=True)
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
        Search for sold/completed listings via Crawl4AI.

        For eBay: appends sold filters. For others: appends "sold" to query.
        """
        if not self.configured:
            return []

        try:
            crawl4ai_circuit.check()
        except CircuitOpenError:
            logger.warning("[Crawl4AICaller] circuit open — skipping sold_comps")
            return []

        from app.lib.crawl4ai_client import scrape_url

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

            wait_for = self._get_wait_selector(site)

            try:
                result = await scrape_url(url, wait_for=wait_for)
                if not result or not result.get("markdown"):
                    continue

                crawl4ai_circuit.record_success()

                listings = _split_into_listings(result["markdown"])
                for listing_text in listings:
                    if len(all_hits) >= limit:
                        break

                    title = _extract_title_from_listing(listing_text)
                    if not title:
                        continue

                    listing_url = _extract_url_from_listing(listing_text) or url
                    price_text = f"{title} {listing_text[:500]}"
                    price, currency, source_price, source_currency = _extract_price(price_text, rates=rates)

                    image_url = _extract_image_url(listing_text)

                    hit: Dict[str, Any] = {
                        "source": "crawl4ai",
                        "raw_id": _content_hash("crawl4ai", listing_url),
                        "title": title[:500],
                        "price": price,
                        "currency": currency,
                        "source_price": source_price,
                        "source_currency": source_currency,
                        "attributes": _extract_attrs_from_text(listing_text),
                        "sold_at": None,
                        "url": listing_url,
                        "condition": None,
                        "image_url": image_url,
                        "is_sold": True,
                        "content_hash": _content_hash("crawl4ai", listing_url),
                    }

                    if hit["price"] is not None:
                        all_hits.append(hit)

            except Exception:
                crawl4ai_circuit.record_failure()
                logger.error("[Crawl4AICaller] sold_comps failed for %s", site, exc_info=True)
                continue

        return all_hits[:limit]

    async def health_check(self) -> bool:
        """Check if Crawl4AI is configured and can scrape a simple page."""
        if not self.configured:
            return False
        try:
            from app.lib.crawl4ai_client import scrape_url
            result = await scrape_url("https://www.example.com")
            return result is not None
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying Crawl4AI browser."""
        try:
            from app.lib.crawl4ai_client import close as c4_close
            await c4_close()
        except ImportError:
            pass
