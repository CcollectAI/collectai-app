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

from app.agents.adapters._jp_proxy import configured as jp_proxy_configured
from app.agents.adapters._jp_proxy import fetch_via_proxy
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

    # Per-listing attributes. Yahoo JP listings carry condition text
    # (e.g. 'used', 'like_new') and seller-type ('store'|'private') —
    # both feed attribute_aggregation_worker for per-item distributions.
    attrs: Dict[str, Any] = {}
    if item.get("condition"):
        attrs["condition"] = item["condition"]
    if item.get("seller_type"):
        attrs["seller_type"] = item["seller_type"]

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
        "attributes": attrs,
    }


def _parse_buyee_html(html: str) -> List[Dict[str, Any]]:
    """Extract listings from Buyee search results HTML.

    Current layout (verified 2026-04-18 via JP Lambda proxy): each result
    is an ``<li class="itemCard">`` containing an ``<a>`` to
    ``/item/jdirectitems/auction/{id}``. Title is in the ``alt`` of the
    thumbnail image. Price is a JPY string somewhere in the card body
    (class varies; we grep the block text).
    """
    listings: List[Dict[str, Any]] = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not available; buyee parsing disabled")
        return listings

    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("li.itemCard")
    for card in cards:
        anchor = card.find("a", href=re.compile(r"/item/[a-z]+/auction/"))
        if not anchor:
            continue
        href = anchor.get("href", "")
        m = re.search(r"/item/[a-z]+/auction/([a-zA-Z0-9]+)", href)
        if not m:
            continue
        item_id = m.group(1)

        # Title: prefer thumbnail alt (carries the full JP title), fall back
        # to the card's visible text stripped.
        img = card.find("img")
        alt = (img.get("alt") or "").strip() if img else ""
        title = alt[:200] if alt else card.get_text(" ", strip=True)[:200]
        if not title:
            continue

        image = img.get("src", "") if img else ""

        # Price — the card body contains at least one ``¥X,XXX`` or ``X,XXX円``.
        card_text = card.get_text(" ", strip=True)
        price = _extract_jpy_price(card_text)

        listings.append({
            "id": item_id,
            "title": title,
            "image": image,
            "price": price or 0,
            "url": f"https://buyee.jp{href}" if href.startswith("/") else href,
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
            encoded_query = quote_plus(query)
            url = f"{BUYEE_SEARCH_URL}/{encoded_query}?translationType=1"

            html = await self._fetch_html(url)
            if not html:
                yahoo_circuit.record_failure()
                return []
            yahoo_circuit.record_success()

            raw_listings = _parse_buyee_html(html)
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
            encoded_query = quote_plus(query)
            url = f"{BUYEE_SEARCH_URL}/{encoded_query}?translationType=1&status=closed"

            html = await self._fetch_html(url)
            if not html:
                yahoo_circuit.record_failure()
                return []
            yahoo_circuit.record_success()

            raw_listings = _parse_buyee_html(html)
            results = [_normalize_listing(item, rates) for item in raw_listings[:limit]]
            for r in results:
                r["is_sold"] = True
            return results

        except Exception as exc:
            yahoo_circuit.record_failure()
            logger.warning("Yahoo Auctions sold comps error: %s", exc)
            return []

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML — prefer JP Lambda proxy when configured, else direct.

        From EU IP, direct requests to buyee.jp return 403 and/or
        Google-Translate wrapper pages. The JP proxy (Lambda in Tokyo)
        returns real content. When JP_PROXY_URL is unset, falls back to
        direct httpx — will typically fail from EU but preserves local
        dev / other-region deployments.
        """
        if jp_proxy_configured():
            html = await fetch_via_proxy(url)
            if html:
                return html
            # Proxy configured but returned None — don't silently fall through
            # to direct (would only re-confirm the EU block).
            return None
        # Direct path (default in environments without the proxy)
        client = await self._client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None

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
