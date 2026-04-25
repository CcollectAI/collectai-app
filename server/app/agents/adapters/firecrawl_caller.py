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
from workers.circuit_breaker import firecrawl_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Site targeting per category
# ---------------------------------------------------------------------------

# Maps CollectAI category IDs to Firecrawl search site: filters
CATEGORY_SITE_TARGETS: Dict[str, List[str]] = {
    # TCGs (Americas + Europe via Cardmarket)
    "pokemon": ["tcgplayer.com", "pricecharting.com", "cardmarket.com", "ebay.com"],
    "mtg": ["tcgplayer.com", "scryfall.com", "cardmarket.com", "ebay.com"],
    "yugioh": ["tcgplayer.com", "pricecharting.com", "cardmarket.com", "ebay.com"],
    "lorcana": ["tcgplayer.com", "pricecharting.com", "cardmarket.com", "ebay.com"],
    # Toys / Figures
    "anime_figures": ["myfigurecollection.net", "amiami.com", "solarisjapan.com", "ebay.com"],
    "blind_box": ["popmart.com", "kidrobot.com", "ebay.com", "stockx.com"],
    "hot_toys": ["sideshow.com", "onesixthwarriors.com", "ebay.com", "collectsideshow.com"],
    "designer_toys": ["stockx.com", "whatnot.com", "ebay.com", "myfigurecollection.net"],
    "funko": ["hobbydb.com", "mercari.com", "poppriceguide.com", "ebay.com"],
    "plush_collectibles": ["squishmallowsquad.com", "mercari.com", "ebay.com", "whatnot.com"],
    # Building / Models
    "lego": ["bricklink.com", "brickset.com", "ebay.com", "rebrickable.com"],
    "gunpla": ["hlj.com", "gundamplanet.com", "amiami.com", "ebay.com"],
    "scale_models": ["scalemates.com", "hlj.com", "ebay.com", "hannants.co.uk"],
    "warhammer": ["thetrolltrader.com", "ebay.com", "blacklibrary.com", "abebooks.com"],
    # Gaming
    "retro_games": ["pricecharting.com", "mercari.com", "ebay.com", "gamevaluenow.com"],
    "retro_handhelds": ["pricecharting.com", "mercari.com", "ebay.com", "gamevaluenow.com"],
    # Media
    "manga": ["mangacollectors.com", "mercari.com", "ebay.com", "bookdepository.com"],
    "comic_books": ["mycomicshop.com", "comicbookrealm.com", "ebay.com", "mercari.com"],
    "bluray_steelbook": ["blu-ray.com", "mercari.com", "ebay.com", "zavvi.com"],
    "anime_bluray": ["blu-ray.com", "cdjapan.co.jp", "amiami.com", "ebay.com"],
    "anime_soundtrack": ["vgmdb.net", "cdjapan.co.jp", "discogs.com", "mercari.com"],
    "anime_ost_vinyl": ["vgmdb.net", "discogs.com", "ebay.com", "merchbar.com"],
    # Music / Fandom
    "kpop_merch": ["mercari.com", "weverse.io", "ktown4u.com", "cokodive.com"],
    "taylor_swift": ["mercari.com", "stockx.com", "ebay.com", "discogs.com"],
    "pop_fandom": ["mercari.com", "stockx.com", "weverse.io", "ktown4u.com"],
    "kpop_lightsticks": ["ktown4u.com", "cokodive.com", "mercari.com", "ebay.com"],
    # Disney / Theme Parks
    "disney": ["shopdisney.com", "mercari.com", "ebay.com", "boxlunch.com"],
    "theme_park": ["ebay.com", "mercari.com", "shopdisney.com", "mercari.com/jp"],
    "ghibli": ["myfigurecollection.net", "ebay.com", "amiami.com", "suruga-ya.jp"],
    # Japan Exclusives
    "bandai_premium": ["myfigurecollection.net", "ebay.com", "amiami.com", "suruga-ya.jp"],
    "jp_magazine": ["ebay.com", "buyee.jp", "mercari.com", "suruga-ya.jp"],
    "jp_event": ["ebay.com", "buyee.jp", "mercari.com", "suruga-ya.jp"],
    # Nintendo / Pokemon Merch
    "nintendo_merch": ["ebay.com", "mercari.com", "amiami.com", "buyee.jp"],
    "retro_pokemon": ["ebay.com", "mercari.com", "amiami.com", "buyee.jp"],
    # IP-Specific
    "one_piece": ["myfigurecollection.net", "mercari.com", "amiami.com", "suruga-ya.jp"],
    "vtuber": ["buyee.jp", "mercari.com", "booth.pm"],
    # Niche
    "keycaps": ["reddit.com/r/mechmarket", "drop.com", "ebay.com", "geekhack.org"],
    "loungefly": ["mercari.com", "stockx.com", "ebay.com", "boxlunch.com"],
    # Lifestyle
    "pens": ["gouletpens.com", "nibs.com", "ebay.com", "penswap.reddit.com"],
    "vinyl_records": ["discogs.com", "vinylmeplease.com", "ebay.com", "reverblp.com"],
    "sneakers": ["stockx.com", "goat.com", "ebay.com", "grailed.com"],
    "vintage_cameras": ["keh.com", "mpb.com", "ebay.com", "japancamerahunter.com"],
    "watches": ["chrono24.com", "watchrecon.com", "ebay.com", "hodinkee.com"],
    "whiskey": ["whiskyauctioneer.com", "thewhiskyexchange.com", "masterofmalt.com", "auction.catawiki.com"],
    # Legacy
    "diecast": ["ebay.com", "diecastmodelswholesale.com", "modelcollect.com", "ebay.co.uk"],
    "sportscards": ["130point.com", "comc.com", "ebay.com", "pwccmarketplace.com"],
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
            firecrawl_circuit.check()
        except CircuitOpenError:
            logger.warning("[FirecrawlCaller] circuit open — skipping search")
            return []

        try:
            results = await search_web(search_query, limit=min(limit, 10))
            hits = [_normalize_search_result(r, query, rates) for r in results]
            firecrawl_circuit.record_success()
            return [h for h in hits if h["price"] is not None]
        except Exception:
            firecrawl_circuit.record_failure()
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
            firecrawl_circuit.check()
        except CircuitOpenError:
            logger.warning("[FirecrawlCaller] circuit open — skipping sold_comps")
            return []

        try:
            results = await search_web(sold_query, limit=min(limit, 10))
            hits = []
            for r in results:
                hit = _normalize_search_result(r, query, rates)
                hit["is_sold"] = True
                if hit["price"] is not None:
                    hits.append(hit)
            firecrawl_circuit.record_success()
            return hits
        except Exception:
            firecrawl_circuit.record_failure()
            logger.error("[FirecrawlCaller] sold_comps failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Structured extraction schema for ML-enriched price extraction
    # ------------------------------------------------------------------

    LISTING_EXTRACT_SCHEMA: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Item title or name"},
            "price": {"type": "number", "description": "Listed price in original currency"},
            "currency": {"type": "string", "description": "Currency code (USD, EUR, GBP, JPY)"},
            "condition": {
                "type": "string",
                "description": "Item condition (Mint, Near Mint, Excellent, Good, Fair, Poor)",
            },
            "seller_name": {"type": "string", "description": "Seller username or store name"},
            "seller_rating": {"type": "number", "description": "Seller rating 0-5"},
            "shipping_cost": {"type": "number", "description": "Shipping cost in same currency"},
            "quantity_available": {"type": "integer", "description": "Number available"},
            "is_sold": {"type": "boolean", "description": "Whether the item has been sold"},
            "attributes": {
                "type": "object",
                "description": "Item-specific attributes",
                "properties": {
                    "set": {"type": "string"},
                    "number": {"type": "string"},
                    "rarity": {"type": "string"},
                    "grade": {"type": "string"},
                    "edition": {"type": "string"},
                    "variant": {"type": "string"},
                },
            },
        },
        "required": ["title"],
    }

    async def search_with_extraction(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search and extract structured listing data from top results.

        Uses Firecrawl's extract_structured API to pull detailed listing
        information (condition, seller rating, attributes) that regex-based
        extraction would miss. More expensive (1 API call per result) so
        use sparingly on high-value queries.
        """
        if not self.configured:
            return []

        from app.lib.firecrawl_client import extract_structured, search_web

        # Fetch live FX rates
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        # First do a quick search to get URLs
        sites = None
        if category and category in CATEGORY_SITE_TARGETS:
            sites = CATEGORY_SITE_TARGETS[category]

        search_query = query
        if sites:
            site_filter = " OR ".join(f"site:{s}" for s in sites[:3])
            search_query = f"{query} ({site_filter})"

        try:
            firecrawl_circuit.check()
        except CircuitOpenError:
            logger.warning("[FirecrawlCaller] circuit open — skipping search_with_extraction")
            return []

        try:
            results = await search_web(search_query, limit=min(limit, 5))
            firecrawl_circuit.record_success()
        except Exception:
            firecrawl_circuit.record_failure()
            logger.error("[FirecrawlCaller] search_with_extraction search failed", exc_info=True)
            return []

        hits = []
        for result in results:
            url = result.get("url", "")
            if not url:
                continue

            try:
                extracted = await extract_structured(url, self.LISTING_EXTRACT_SCHEMA)
                if not extracted:
                    # Fall back to regex-based extraction
                    hits.append(_normalize_search_result(result, query, rates))
                    continue

                # Build enriched hit from structured data
                title = extracted.get("title", result.get("title", query))
                raw_price = extracted.get("price")
                raw_currency = (extracted.get("currency") or "EUR").upper()

                if raw_price and raw_price > 0:
                    _rates = rates or {}
                    if raw_currency == "USD":
                        price_eur = round(raw_price * _rates.get("USD", USD_TO_EUR), 2)
                    elif raw_currency == "GBP":
                        price_eur = round(raw_price * _rates.get("GBP", GBP_TO_EUR), 2)
                    elif raw_currency == "JPY":
                        price_eur = round(raw_price * _rates.get("JPY", JPY_TO_EUR), 2)
                    else:
                        price_eur = raw_price
                else:
                    # Fall back to regex extraction
                    price_text = f"{title} {result.get('markdown', '')[:500]}"
                    price_eur, _, _, _ = _extract_price(price_text, rates)

                if price_eur is None or price_eur <= 0:
                    continue

                hit = {
                    "source": "firecrawl_ml",
                    "raw_id": _content_hash("firecrawl_ml", url),
                    "title": title[:500],
                    "price": price_eur,
                    "currency": "EUR",
                    "source_price": raw_price,
                    "source_currency": raw_currency,
                    "url": url,
                    "condition": extracted.get("condition"),
                    "seller": extracted.get("seller_name"),
                    "seller_rating": extracted.get("seller_rating"),
                    "shipping_cost": extracted.get("shipping_cost"),
                    "quantity_available": extracted.get("quantity_available"),
                    "is_sold": extracted.get("is_sold", False),
                    "image_url": _extract_image_url(result.get("markdown", "")),
                    "content_hash": _content_hash("firecrawl_ml", url),
                    "attributes": extracted.get("attributes", {}),
                    "extraction_method": "structured",
                }
                hits.append(hit)

            except Exception:
                logger.debug("[FirecrawlCaller] extraction failed for %s", url, exc_info=True)
                # Fall back to regex
                fallback = _normalize_search_result(result, query, rates)
                if fallback.get("price") is not None:
                    hits.append(fallback)

        return hits

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
