"""
Mandarake marketplace adapter for the Marketplace Aggregation Agent.

Mandarake (mandarake.co.jp) is Japan's largest secondhand anime/collectibles
retailer with extensive online listings. This adapter scrapes Mandarake search
results to extract active listing prices, primarily in JPY.

Covers Japan-focused collectible categories: anime_figures, bandai_premium,
ghibli, jp_event, jp_magazine, hot_toys, gunpla, designer_toys, manga, vtuber.

Env vars:
    MANDARAKE_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import mandarake_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

MANDARAKE_SOURCE_RELIABILITY = 0.75

# Mandarake search URL (English version)
MANDARAKE_SEARCH_URL = "https://order.mandarake.co.jp/order/listPage/list"

# Mandarake item detail URL
MANDARAKE_DETAIL_URL = "https://order.mandarake.co.jp/order/detailPage/item"

# Categories that Mandarake excels in
SUPPORTED_CATEGORIES = [
    "anime_figures",
    "bandai_premium",
    "ghibli",
    "jp_event",
    "jp_magazine",
    "hot_toys",
    "gunpla",
    "designer_toys",
    "manga",
    "vtuber",
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
    # Remove "税込" (tax included), full-width/half-width parens, and other suffixes
    cleaned = re.sub(r"[（）()税込抜]", "", cleaned)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_listing(
    item_code: str,
    title: str,
    jpy_price: float,
    condition: Optional[str],
    image_url: str,
) -> Dict[str, Any]:
    """Normalize a Mandarake listing to the standard MarketHit format."""
    eur_price = _convert_jpy_to_eur(jpy_price)
    item_url = f"{MANDARAKE_DETAIL_URL}?itemCode={item_code}&lang=en" if item_code else MANDARAKE_SEARCH_URL

    return {
        "source": "mandarake",
        "raw_id": f"mandarake-{item_code}",
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


class MandarakeCaller:
    """Async Mandarake adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("MANDARAKE_ENABLED", "true").lower() == "true"
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
        """Search Mandarake for active listings."""
        if not self.configured:
            return []

        try:
            mandarake_circuit.check()
        except CircuitOpenError:
            logger.warning("Mandarake circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                MANDARAKE_SEARCH_URL,
                params={
                    "keyword": query,
                    "lang": "en",
                },
            )

            if resp.status_code != 200:
                mandarake_circuit.record_failure()
                logger.warning("Mandarake search returned %d", resp.status_code)
                return []

            mandarake_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            mandarake_circuit.record_failure()
            logger.warning("Mandarake search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Mandarake search results from HTML.

        Mandarake's search page contains item blocks with:
        - itemCode in links (e.g., itemCode=nitem-00XXXXXXXX)
        - Titles in <p> or <div> elements
        - Prices in JPY (e.g., 3,500円)
        - Condition labels (e.g., 中古/Used, 新品/New)
        - Image URLs from <img> tags
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract item blocks — Mandarake uses itemCode= in detail links
        item_code_pattern = re.compile(
            r'itemCode=([a-zA-Z0-9-]+)',
        )

        # Price pattern — JPY prices like "3,500円" or "¥3,500"
        price_pattern = re.compile(
            r'(?:¥|\\u00a5)?\s*(\d{1,3}(?:,\d{3})*)\s*(?:円)?',
        )

        # Title pattern — Mandarake uses class="title" or similar
        title_pattern = re.compile(
            r'class="[^"]*(?:title|itemName|goods_name)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern — Mandarake image URLs
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*mandarake[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Condition patterns — Japanese and English
        condition_map = {
            "新品": "New",
            "未開封": "New/Sealed",
            "美品": "Like New",
            "中古": "Used",
            "難あり": "Fair",
            "ジャンク": "Poor",
            "A": "Like New",
            "B": "Good",
            "C": "Fair",
        }

        # Extract unique item codes
        item_codes = list(dict.fromkeys(item_code_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        # Try to detect conditions from the page
        condition_pattern = re.compile(
            r'(?:condition|状態|ランク)[^>]*>([^<]+)<',
            re.IGNORECASE,
        )
        conditions = condition_pattern.findall(html)

        for i, item_code in enumerate(item_codes):
            # Title
            title = titles[i].strip() if i < len(titles) else f"Mandarake item {item_code}"

            # Price
            jpy_price = 0.0
            if i < len(prices):
                try:
                    jpy_price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # Condition
            condition = None
            if i < len(conditions):
                cond_text = conditions[i].strip()
                for jp_key, en_val in condition_map.items():
                    if jp_key in cond_text:
                        condition = en_val
                        break
                if not condition and cond_text:
                    condition = cond_text

            results.append(
                _normalize_listing(item_code, title, jpy_price, condition, image_url)
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        Mandarake does not expose sold history publicly — all items on
        their site are current active listings. Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                MANDARAKE_SEARCH_URL,
                params={"keyword": "test", "lang": "en"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
