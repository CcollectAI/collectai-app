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

from app.config import USD_TO_EUR, JPY_TO_EUR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Site targeting per category
# ---------------------------------------------------------------------------

# Maps CollectAI category IDs to Firecrawl search site: filters
CATEGORY_SITE_TARGETS: Dict[str, List[str]] = {
    "anime_figures": ["myfigurecollection.net", "amiami.com", "solarisjapan.com"],
    "scale_models": ["scalemates.com", "hlj.com"],
    "gunpla": ["hlj.com", "gundamplanet.com"],
    "keycaps": ["reddit.com/r/mechmarket", "drop.com"],
    "anime_soundtrack": ["vgmdb.net", "cdjapan.co.jp"],
    "anime_ost_vinyl": ["vgmdb.net", "discogs.com"],
    "diecast": ["ebay.com", "diecastmodelswholesale.com"],
    "retro_games": ["pricecharting.com", "mercari.com"],
    "manga": ["mangacollectors.com", "mercari.com"],
    "kpop_merch": [
        "mercari.com", "weverse.io", "ktown4u.com",
        "reddit.com/r/kpopforsale",
    ],
    "taylor_swift": [
        "mercari.com", "stockx.com",
        "reddit.com/r/TaylorSwiftMerch",
    ],
    "pop_fandom": ["mercari.com", "stockx.com"],
    "kpop_lightsticks": ["ktown4u.com", "mercari.com"],
    "lego": ["bricklink.com", "brickset.com"],
    "one_piece": ["myfigurecollection.net", "mercari.com"],
    "vtuber": ["buyee.jp", "mercari.com"],
    "loungefly": ["mercari.com", "stockx.com"],
    "disney": ["shopdisney.com", "mercari.com"],
    "hot_toys": ["sideshow.com", "onesixthwarriors.com"],
    "designer_toys": ["stockx.com", "whatnot.com"],
    "sportscards": ["130point.com", "comc.com"],
    "funko": ["hobbydb.com", "mercari.com"],
    "warhammer": ["thetrolltrader.com", "ebay.com"],
    "bluray_steelbook": ["blu-ray.com", "mercari.com"],
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
    # 12,99 EUR or EUR 12.99
    re.compile(r"(?:EUR)\s*(\d[\d,]*\.?\d*)", re.IGNORECASE),
    re.compile(r"(\d[\d,]*\.?\d*)\s*(?:EUR)", re.IGNORECASE),
    # JPY / Yen
    re.compile(r"[¥￥]\s*(\d[\d,]*)", re.IGNORECASE),
    re.compile(r"(\d[\d,]*)\s*(?:JPY|yen)", re.IGNORECASE),
    # Generic price
    re.compile(r"(\d{1,6}\.\d{2})\b"),
]


def _extract_price(text: str) -> tuple[Optional[float], str]:
    """Extract the first recognizable price from text. Returns (price_eur, currency)."""
    if not text:
        return None, "EUR"

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
                return round(price * USD_TO_EUR, 2), "EUR"
            if "¥" in full_match or "￥" in full_match or "JPY" in full_match.upper():
                return round(price * JPY_TO_EUR, 2), "EUR"
            return price, "EUR"

    return None, "EUR"


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
) -> Dict[str, Any]:
    """Normalize a Firecrawl search result to our standard MarketHit dict."""
    url = result.get("url", "")
    title = result.get("title") or result.get("metadata", {}).get("title", "")
    markdown = result.get("markdown", "")
    description = result.get("description") or result.get("metadata", {}).get("description", "")

    # Extract price from title, description, or markdown
    price_text = f"{title} {description} {markdown[:1000]}"
    price, currency = _extract_price(price_text)

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
    ) -> List[Dict[str, Any]]:
        """
        Search the web for marketplace listings via Firecrawl.

        Targets category-specific sites when a category is provided.
        Returns normalized MarketHit dicts.
        """
        if not self.configured:
            logger.debug("[FirecrawlCaller] Not configured (no FIRECRAWL_API_KEY)")
            return []

        from app.lib.firecrawl_client import search_web

        # Build site-targeted query
        search_query = query
        if category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]
            site_filter = " OR ".join(f"site:{s}" for s in sites[:3])
            search_query = f"{query} ({site_filter})"
        else:
            # Generic marketplace search
            search_query = f"{query} price listing"

        try:
            results = await search_web(search_query, limit=min(limit, 10))
            hits = [_normalize_search_result(r, query) for r in results]
            # Filter out results with no price
            return [h for h in hits if h["price"] is not None]
        except Exception:
            logger.error("[FirecrawlCaller] search failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for sold/completed listings via Firecrawl.

        Appends "sold" to the query to target completed listings.
        """
        if not self.configured:
            return []

        from app.lib.firecrawl_client import search_web

        sold_query = f"{query} sold completed price"
        if category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]
            site_filter = " OR ".join(f"site:{s}" for s in sites[:3])
            sold_query = f"{query} sold ({site_filter})"

        try:
            results = await search_web(sold_query, limit=min(limit, 10))
            hits = []
            for r in results:
                hit = _normalize_search_result(r, query)
                hit["is_sold"] = True  # Mark as sold since we searched for sold items
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
