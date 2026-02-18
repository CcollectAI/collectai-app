"""
Firecrawl marketplace adapter for the Marketplace Aggregation Agent.

Uses Firecrawl /search to find listings on sites that lack dedicated APIs:
- Mercari JP, Yahoo Auctions JP, BrickLink, MyFigureCollection, VGMdb,
  StockX, Reddit r/mechmarket, BTS/K-pop fan marketplaces, Taylor Swift merch

Maps search results to the same MarketHit dict format as ebay_caller and
tcgplayer_caller so the marketplace agent can deduplicate and score them.

Env vars:
    FIRECRAWL_API_KEY  - Firecrawl API key
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import USD_TO_EUR, GBP_TO_EUR, JPY_TO_EUR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Site targeting per category
# ---------------------------------------------------------------------------

# Maps CollectAI category IDs to Firecrawl search site: filters
CATEGORY_SITE_TARGETS: Dict[str, List[str]] = {
    # TCGs (Americas defaults — TCGPlayer handles primary search)
    "pokemon": ["tcgplayer.com", "pricecharting.com"],
    "mtg": ["tcgplayer.com", "scryfall.com"],
    "yugioh": ["tcgplayer.com", "pricecharting.com"],
    "lorcana": ["tcgplayer.com", "pricecharting.com"],
    # Toys / Figures
    "anime_figures": ["myfigurecollection.net", "amiami.com", "solarisjapan.com"],
    "hot_toys": ["sideshow.com", "onesixthwarriors.com"],
    "designer_toys": ["stockx.com", "whatnot.com"],
    "funko": ["hobbydb.com", "mercari.com"],
    # Building / Models
    "lego": ["bricklink.com", "brickset.com"],
    "gunpla": ["hlj.com", "gundamplanet.com"],
    "scale_models": ["scalemates.com", "hlj.com"],
    "warhammer": ["thetrolltrader.com", "ebay.com"],
    # Gaming
    "retro_games": ["pricecharting.com", "mercari.com"],
    "retro_handhelds": ["pricecharting.com", "mercari.com"],
    # Media
    "manga": ["mangacollectors.com", "mercari.com"],
    "bluray_steelbook": ["blu-ray.com", "mercari.com"],
    "anime_bluray": ["blu-ray.com", "cdjapan.co.jp"],
    "anime_soundtrack": ["vgmdb.net", "cdjapan.co.jp"],
    "anime_ost_vinyl": ["vgmdb.net", "discogs.com"],
    # Music / Fandom
    "kpop_merch": ["mercari.com", "weverse.io", "ktown4u.com"],
    "taylor_swift": ["mercari.com", "stockx.com"],
    "pop_fandom": ["mercari.com", "stockx.com"],
    "kpop_lightsticks": ["ktown4u.com", "mercari.com"],
    # Disney / Theme Parks
    "disney": ["shopdisney.com", "mercari.com"],
    "theme_park": ["ebay.com", "mercari.com"],
    "ghibli": ["myfigurecollection.net", "ebay.com"],
    # Japan Exclusives
    "bandai_premium": ["myfigurecollection.net", "ebay.com"],
    "jp_magazine": ["ebay.com", "buyee.jp"],
    "jp_event": ["ebay.com", "buyee.jp"],
    # Nintendo / Pokemon Merch
    "nintendo_merch": ["ebay.com", "mercari.com"],
    "retro_pokemon": ["ebay.com", "mercari.com"],
    # IP-Specific
    "one_piece": ["myfigurecollection.net", "mercari.com"],
    "vtuber": ["buyee.jp", "mercari.com"],
    # Niche
    "keycaps": ["reddit.com/r/mechmarket", "drop.com"],
    "loungefly": ["mercari.com", "stockx.com"],
    # Legacy
    "diecast": ["ebay.com", "diecastmodelswholesale.com"],
    "sportscards": ["130point.com", "comc.com"],
}

# Provenance score for Firecrawl web-scraped results (lower than direct APIs)
FIRECRAWL_SOURCE_RELIABILITY = 0.65

# FX rates imported from app.config: USD_TO_EUR, JPY_TO_EUR


# ---------------------------------------------------------------------------
# Price extraction helpers
# ---------------------------------------------------------------------------

_PRICE_PATTERNS = [
    # $12.99 or USD 12.99
    re.compile(r"(?:USD|\$)\s*(\d[\d,]*\.?\d*)", re.IGNORECASE),
    # £12.99 or GBP 12.99
    re.compile(r"(?:GBP|£)\s*(\d[\d,]*\.?\d*)", re.IGNORECASE),
    re.compile(r"(\d[\d,]*\.?\d*)\s*(?:GBP)", re.IGNORECASE),
    # 12,99 EUR or EUR 12.99 or €12.99
    re.compile(r"(?:EUR|€)\s*(\d[\d,]*\.?\d*)", re.IGNORECASE),
    re.compile(r"(\d[\d,]*\.?\d*)\s*(?:EUR|€)", re.IGNORECASE),
    # JPY / Yen
    re.compile(r"[¥￥]\s*(\d[\d,]*)", re.IGNORECASE),
    re.compile(r"(\d[\d,]*)\s*(?:JPY|yen)", re.IGNORECASE),
    # Generic price
    re.compile(r"(\d{1,6}\.\d{2})\b"),
]


def _extract_price(
    text: str,
    rates: dict[str, float] | None = None,
) -> tuple[Optional[float], str, Optional[float], Optional[str]]:
    """Extract the first recognizable price from text.

    Returns (price_eur, currency, source_price, source_currency).
    *rates* is a foreign→EUR dict.  Falls back to config defaults.
    """
    if not text:
        return None, "EUR", None, None

    _rates = rates or {}

    for pattern in _PRICE_PATTERNS:
        m = pattern.search(text)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                price = float(raw)
            except ValueError:
                continue

            full_match = m.group(0)
            if "$" in full_match or "USD" in full_match.upper():
                rate = _rates.get("USD", USD_TO_EUR)
                return round(price * rate, 2), "EUR", price, "USD"
            if "£" in full_match or "GBP" in full_match.upper():
                rate = _rates.get("GBP", GBP_TO_EUR)
                return round(price * rate, 2), "EUR", price, "GBP"
            if "¥" in full_match or "￥" in full_match or "JPY" in full_match.upper():
                rate = _rates.get("JPY", JPY_TO_EUR)
                return round(price * rate, 2), "EUR", price, "JPY"
            if "€" in full_match or "EUR" in full_match.upper():
                return price, "EUR", price, "EUR"
            # Generic (assume EUR)
            return price, "EUR", price, "EUR"

    return None, "EUR", None, None


def _content_hash(source: str, url: str) -> str:
    """Compute SHA-256 content hash for deduplication."""
    payload = f"{source}:{url}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_image_url(markdown: str) -> Optional[str]:
    """Extract the first image URL from markdown content."""
    m = re.search(r"!\[.*?\]\((https?://[^\s)]+)\)", markdown or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_search_result(
    result: Dict[str, Any],
    query: str,
    rates: dict[str, float] | None = None,
) -> Dict[str, Any]:
    """Normalize a Firecrawl search result to our standard MarketHit dict."""
    url = result.get("url", "")
    title = result.get("title") or result.get("metadata", {}).get("title", "")
    markdown = result.get("markdown", "")
    description = result.get("description") or result.get("metadata", {}).get("description", "")

    # Extract price from title, description, or markdown
    price_text = f"{title} {description} {markdown[:1000]}"
    price, currency, source_price, source_currency = _extract_price(price_text, rates)

    # Extract image
    image_url = _extract_image_url(markdown)

    # Determine if likely sold (heuristic based on keywords)
    sold_keywords = ["sold", "completed", "ended", "past sale"]
    is_sold = any(kw in (title + description).lower() for kw in sold_keywords)

    return {
        "source": "firecrawl",
        "raw_id": _content_hash("firecrawl", url),
        "title": title[:500] if title else query,
        "price": price,
        "currency": currency,
        "source_price": source_price,
        "source_currency": source_currency,
        "sold_at": None,
        "url": url,
        "condition": None,
        "image_url": image_url,
        "is_sold": is_sold,
        "content_hash": _content_hash("firecrawl", url),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class FirecrawlCaller:
    """Async Firecrawl web search caller for the marketplace aggregation agent."""

    def __init__(self) -> None:
        pass

    @property
    def configured(self) -> bool:
        try:
            from app.lib.firecrawl_client import configured as fc_configured
            return fc_configured()
        except ImportError:
            return False

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region_sites: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the web for marketplace listings via Firecrawl.

        Targets category-specific sites when a category is provided.
        *region_sites* overrides the global CATEGORY_SITE_TARGETS when set.
        Returns normalized MarketHit dicts.
        """
        if not self.configured:
            logger.debug("[FirecrawlCaller] Not configured (no FIRECRAWL_API_KEY)")
            return []

        from app.lib.firecrawl_client import search_web

        # Fetch live FX rates once for this call
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        # Build site-targeted query
        search_query = query
        sites = region_sites  # prefer region override
        if not sites and category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]

        if sites:
            site_filter = " OR ".join(f"site:{s}" for s in sites[:3])
            search_query = f"{query} ({site_filter})"
        else:
            search_query = f"{query} price listing"

        try:
            results = await search_web(search_query, limit=min(limit, 10))
            hits = [_normalize_search_result(r, query, rates) for r in results]
            return [h for h in hits if h["price"] is not None]
        except Exception:
            logger.error("[FirecrawlCaller] search failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        region_sites: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for sold/completed listings via Firecrawl.

        Appends "sold" to the query to target completed listings.
        *region_sites* overrides the global CATEGORY_SITE_TARGETS when set.
        """
        if not self.configured:
            return []

        from app.lib.firecrawl_client import search_web

        # Fetch live FX rates once for this call
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        sites = region_sites
        if not sites and category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]

        sold_query = f"{query} sold completed price"
        if sites:
            site_filter = " OR ".join(f"site:{s}" for s in sites[:3])
            sold_query = f"{query} sold ({site_filter})"

        try:
            results = await search_web(sold_query, limit=min(limit, 10))
            hits = []
            for r in results:
                hit = _normalize_search_result(r, query, rates)
                hit["is_sold"] = True
                if hit["price"] is not None:
                    hits.append(hit)
            return hits
        except Exception:
            logger.error("[FirecrawlCaller] sold_comps failed", exc_info=True)
            return []

    async def health_check(self) -> bool:
        """Check if Firecrawl API is reachable."""
        if not self.configured:
            return False
        try:
            from app.lib.firecrawl_client import search_web
            results = await search_web("collectible", limit=1)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        try:
            from app.lib.firecrawl_client import close as fc_close
            await fc_close()
        except ImportError:
            pass
