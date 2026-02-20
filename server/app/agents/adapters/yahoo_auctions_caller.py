"""
Yahoo Auctions Japan caller for the Marketplace Aggregation Agent.

Yahoo Auctions Japan (ヤフオク) is the largest auction platform in Japan.
Critical for Japanese exclusive collectibles: bandai_premium, jp_event,
jp_magazine, ghibli, anime_figures, retro_pokemon, vtuber, gunpla.

Since Yahoo Auctions JP doesn't have a public API for external apps,
this adapter uses Buyee's search interface (a proxy for Yahoo Auctions
that supports international buyers) via HTTP scraping.

Env vars:
    YAHOO_AUCTIONS_ENABLED - Enable Yahoo Auctions adapter (true/false)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUYEE_SEARCH_URL = "https://buyee.jp/item/search/query"
BUYEE_ITEM_URL = "https://buyee.jp/item/yahoo/auction"

# Create a local circuit breaker for Yahoo Auctions
yahoo_circuit = CircuitBreaker("yahoo_auctions", max_failures=5, cooldown_seconds=120)

# Categories that benefit most from Yahoo Auctions JP data
SUPPORTED_CATEGORIES = [
    "bandai_premium",
    "jp_event",
    "jp_magazine",
    "ghibli",
    "anime_figures",
    "retro_pokemon",
    "vtuber",
    "gunpla",
    "anime_bluray",
    "anime_soundtrack",
    "anime_ost_vinyl",
    "one_piece",
    "hot_toys",
    "nintendo_merch",
    "kpop_merch",
    "keycaps",
    "scale_models",
    "warhammer",
]

YAHOO_AUCTIONS_SOURCE_RELIABILITY = 0.70

# JPY to EUR rough default (overridden by live FX when available)
DEFAULT_JPY_TO_EUR = 0.0062


# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r'¥\s*([\d,]+)')
_JPY_NUM_RE = re.compile(r'([\d,]+)\s*円')


def _extract_jpy_price(text: str) -> Optional[float]:
    """Extract JPY price from text."""
    for pattern in (_PRICE_RE, _JPY_NUM_RE):
        m = pattern.search(text)
        if m:
            return float(m.group(1).replace(",", ""))
    # Try plain number
    m = re.search(r'(\d[\d,]*)', text)
    if m:
        val = float(m.group(1).replace(",", ""))
        if val >= 100:  # Likely JPY if >= 100
            return val
    return None


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_listing(item: Dict[str, Any], rates: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Normalize a Yahoo Auctions/Buyee listing into a standard MarketHit dict."""
    title = item.get("title", "Unknown")
    price_jpy = item.get("price", 0)
    image = item.get("image", "")
    item_id = item.get("id", "")
    url = item.get("url") or f"{BUYEE_ITEM_URL}/{item_id}"
    bids = item.get("bids", 0)
    end_time = item.get("end_time")

    # Convert JPY → EUR
    jpy_rate = (rates or {}).get("JPY", DEFAULT_JPY_TO_EUR)
    price_eur = round(float(price_jpy) * jpy_rate, 2) if price_jpy else 0

    return {
        "source": "yahoo_auctions_jp",
        "raw_id": f"yahoo-jp-{item_id}",
        "title": title,
        "price": price_eur,
        "price_jpy": float(price_jpy) if price_jpy else 0,
        "currency": "EUR",
        "source_price": float(price_jpy) if price_jpy else 0,
        "source_currency": "JPY",
        "url": url,
        "condition": item.get("condition"),
        "image_url": image,
        "is_sold": item.get("is_sold", False),
        "bids": bids,
        "end_time": end_time,
        "seller": item.get("seller"),
    }


def _parse_buyee_html(html: str) -> List[Dict[str, Any]]:
    """Extract listings from Buyee search results HTML.

    This is a lightweight parser — for production, pair with Firecrawl
    or Crawl4AI for more robust extraction.
    """
    listings: List[Dict[str, Any]] = []

    # Split by item blocks (common Buyee patterns)
    # Look for item links and price blocks
    item_pattern = re.compile(
        r'<a[^>]+href="[^"]*?/item/yahoo/auction/([a-zA-Z0-9]+)"[^>]*>'
        r'.*?'
        r'<(?:img|picture)[^>]+src="([^"]*)"'
        r'.*?'
        r'>(.*?)</a>',
        re.DOTALL,
    )

    for match in item_pattern.finditer(html):
        item_id, image, body = match.groups()
        # Extract title (strip HTML tags)
        title = re.sub(r'<[^>]+>', '', body).strip()[:200]
        if not title:
            continue

        # Try to find price near this listing
        price = _extract_jpy_price(body)

        listings.append({
            "id": item_id,
            "title": title,
            "image": image,
            "price": price or 0,
            "url": f"{BUYEE_ITEM_URL}/{item_id}",
        })

    return listings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class YahooAuctionsCaller:
    """Async Yahoo Auctions JP caller via Buyee proxy."""

    def __init__(self, enabled: Optional[bool] = None):
        if enabled is not None:
            self._enabled = enabled
        else:
            self._enabled = os.getenv("YAHOO_AUCTIONS_ENABLED", "false").lower() in ("1", "true", "yes")
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=25.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; CollectAI/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
                },
                follow_redirects=True,
            )
        return self._http

    async def search(
        self,
        query: str,
        category: str = "anime_figures",
        limit: int = 25,
        rates: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Search Yahoo Auctions JP via Buyee for items matching a query."""
        if not self.configured:
            logger.debug("Yahoo Auctions not enabled — skipping")
            return []

        try:
            yahoo_circuit.check()
        except CircuitOpenError:
            logger.warning("Yahoo Auctions circuit open — skipping")
            return []

        try:
            client = await self._client()
            encoded_query = quote_plus(query)
            url = f"{BUYEE_SEARCH_URL}/{encoded_query}"

            resp = await client.get(url, params={"translationType": "1"})
            resp.raise_for_status()
            yahoo_circuit.record_success()

            raw_listings = _parse_buyee_html(resp.text)
            return [_normalize_listing(item, rates) for item in raw_listings[:limit]]

        except Exception as exc:
            yahoo_circuit.record_failure()
            logger.warning("Yahoo Auctions search error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: str = "anime_figures",
        limit: int = 25,
        rates: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Search ended/sold auctions on Yahoo Auctions JP."""
        if not self.configured:
            return []

        try:
            yahoo_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            encoded_query = quote_plus(query)
            url = f"{BUYEE_SEARCH_URL}/{encoded_query}"

            resp = await client.get(url, params={"translationType": "1", "status": "closed"})
            resp.raise_for_status()
            yahoo_circuit.record_success()

            raw_listings = _parse_buyee_html(resp.text)
            results = [_normalize_listing(item, rates) for item in raw_listings[:limit]]
            for r in results:
                r["is_sold"] = True
            return results

        except Exception as exc:
            yahoo_circuit.record_failure()
            logger.warning("Yahoo Auctions sold comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get("https://buyee.jp/", timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
