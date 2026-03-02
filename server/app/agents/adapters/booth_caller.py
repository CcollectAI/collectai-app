"""
Booth.pm marketplace adapter for the Marketplace Aggregation Agent.

Booth.pm (booth.pm) is a Japanese indie/doujin marketplace, and a major hub
for VTuber merchandise, indie designer toys, and fan-made collectibles.
This adapter scrapes Booth search results to extract active listing prices,
primarily in JPY.

Covers Japan-focused collectible categories: vtuber, jp_event, designer_toys,
kpop_lightsticks.

Env vars:
    BOOTH_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import booth_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

BOOTH_SOURCE_RELIABILITY = 0.70

# Booth search URL (English version)
BOOTH_SEARCH_URL = "https://booth.pm/en/items"

# Booth item detail URL
BOOTH_DETAIL_URL = "https://booth.pm/en/items"

# Categories that Booth excels in
SUPPORTED_CATEGORIES = [
    "vtuber",
    "jp_event",
    "designer_toys",
    "kpop_lightsticks",
]

# JPY to EUR fallback rate (used when import_common is unavailable)
_FALLBACK_JPY_TO_EUR = 0.0062


def _convert_jpy_to_eur(jpy_price: float) -> float:
    """Convert JPY price to EUR using live rates with fallback."""
    try:
        from pipelines.import_common import to_eur
        return to_eur(jpy_price, "JPY")
    except Exception:
        return round(jpy_price * _FALLBACK_JPY_TO_EUR, 2)


def _parse_price(price_str: str) -> float:
    """Parse a JPY price string like '3,500円' or '¥3500' into a float."""
    if not price_str:
        return 0.0
    # Remove currency symbols, commas, spaces, and yen character
    cleaned = re.sub(r"[¥円,\s\u00a5]", "", price_str)
    # Remove other non-numeric characters
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_listing(
    item_id: str,
    title: str,
    jpy_price: float,
    condition: Optional[str],
    image_url: str,
) -> Dict[str, Any]:
    """Normalize a Booth listing to the standard MarketHit format."""
    eur_price = _convert_jpy_to_eur(jpy_price)
    item_url = f"{BOOTH_DETAIL_URL}/{item_id}" if item_id else BOOTH_SEARCH_URL

    return {
        "source": "booth",
        "raw_id": f"booth-{item_id}",
        "title": title[:500],
        "price": eur_price,
        "currency": "EUR",
        "source_price": jpy_price,
        "source_currency": "JPY",
        "url": item_url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class BoothCaller:
    """Async Booth.pm adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("BOOTH_ENABLED", "true").lower() == "true"
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
                },
                follow_redirects=True,
            )
        return self._http

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Booth.pm for active listings."""
        if not self.configured:
            return []

        try:
            booth_circuit.check()
        except CircuitOpenError:
            logger.warning("Booth circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                BOOTH_SEARCH_URL,
                params={
                    "keyword": query,
                },
            )

            if resp.status_code != 200:
                booth_circuit.record_failure()
                logger.warning("Booth search returned %d", resp.status_code)
                return []

            booth_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            booth_circuit.record_failure()
            logger.warning("Booth search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Booth.pm search results from HTML.

        Booth's search page contains item cards with:
        - Item IDs in links (e.g., /items/1234567)
        - Titles in heading elements
        - Prices in JPY (e.g., ¥3,500)
        - Image URLs from <img> tags
        - Most items are new/handmade indie goods
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract item IDs from links — Booth uses /items/NUMERIC_ID
        item_id_pattern = re.compile(
            r'/items/(\d+)',
        )

        # Price pattern — JPY prices like "¥3,500" or "3,500円"
        price_pattern = re.compile(
            r'(?:¥|\\u00a5)?\s*(\d{1,3}(?:,\d{3})*)\s*(?:円)?',
        )

        # Title pattern — Booth uses class containing "item-card" or "shop-item"
        title_pattern = re.compile(
            r'class="[^"]*(?:item-card__title|shop-item-name|item-name|item_card_title)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern — Booth image URLs (booth.pm CDN)
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:booth|s2\.booth)[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Extract unique item IDs
        item_ids = list(dict.fromkeys(item_id_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        for i, item_id in enumerate(item_ids):
            # Title
            title = titles[i].strip() if i < len(titles) else f"Booth item {item_id}"

            # Price
            jpy_price = 0.0
            if i < len(prices):
                try:
                    jpy_price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # Most Booth items are new (indie/doujin goods)
            condition = "New"

            results.append(
                _normalize_listing(item_id, title, jpy_price, condition, image_url)
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        Booth.pm does not expose sold history publicly — all items on
        the site are current active listings. Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                BOOTH_SEARCH_URL,
                params={"keyword": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
