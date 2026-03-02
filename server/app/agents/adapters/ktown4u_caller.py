"""
KTown4U marketplace adapter for the Marketplace Aggregation Agent.

KTown4U (ktown4u.com) is a leading Korean pop culture merchandise retailer
specializing in K-pop albums, merchandise, lightsticks, and related goods.
This adapter scrapes KTown4U search results to extract active listing prices,
primarily in KRW.

Covers K-pop-focused categories: kpop, kpop_lightsticks, blind_box.

Env vars:
    KTOWN4U_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import ktown4u_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

KTOWN4U_SOURCE_RELIABILITY = 0.75

# KTown4U search URL
KTOWN4U_SEARCH_URL = "https://www.ktown4u.com/search"

# Categories that KTown4U excels in
SUPPORTED_CATEGORIES = [
    "kpop",
    "kpop_lightsticks",
    "blind_box",
]

# KRW to EUR fallback rate (used when import_common is unavailable)
_FALLBACK_KRW_TO_EUR = 0.00067


def _convert_krw_to_eur(krw_price: float) -> float:
    """Convert KRW price to EUR using live rates with fallback."""
    try:
        from pipelines.import_common import to_eur
        result = to_eur(krw_price, "KRW")
        # to_eur returns price as-is if currency is unknown; detect and use fallback
        if krw_price > 100 and result == krw_price:
            return round(krw_price * _FALLBACK_KRW_TO_EUR, 2)
        return result
    except Exception:
        return round(krw_price * _FALLBACK_KRW_TO_EUR, 2)


def _parse_krw_price(text: str) -> float:
    """Extract a KRW price from text like '₩25,000', '25,000원', 'KRW 25000'."""
    if not text:
        return 0.0

    patterns = [
        r'[₩\u20a9]([\d,]+)',              # ₩ symbol
        r'([\d,]+)\s*원',                    # 원 (won) suffix
        r'KRW\s*([\d,]+)',                   # KRW prefix
        r'krw\s*([\d,]+)',                   # krw lowercase
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (ValueError, TypeError):
                continue

    # Fallback: try to find a bare number that looks like KRW (typically 4-7 digits)
    bare = re.search(r'(\d{4,7})', text.replace(",", ""))
    if bare:
        try:
            return float(bare.group(1))
        except (ValueError, TypeError):
            pass

    return 0.0


def _normalize_listing(
    product_id: str,
    title: str,
    krw_price: float,
    condition: Optional[str],
    image_url: str,
) -> Dict[str, Any]:
    """Normalize a KTown4U listing to the standard MarketHit format."""
    eur_price = _convert_krw_to_eur(krw_price)
    item_url = f"https://www.ktown4u.com/iteminfo?goods_no={product_id}" if product_id else KTOWN4U_SEARCH_URL

    return {
        "source": "ktown4u",
        "raw_id": f"ktown4u-{product_id}",
        "title": title[:500],
        "price": eur_price,
        "currency": "EUR",
        "source_price": krw_price,
        "source_currency": "KRW",
        "url": item_url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class KTown4UCaller:
    """Async KTown4U adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("KTOWN4U_ENABLED", "true").lower() == "true"
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
                    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
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
        """Search KTown4U for active listings."""
        if not self.configured:
            return []

        try:
            ktown4u_circuit.check()
        except CircuitOpenError:
            logger.warning("KTown4U circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                KTOWN4U_SEARCH_URL,
                params={"goodsTextSearch": query},
            )

            if resp.status_code in (429, 503):
                ktown4u_circuit.record_failure()
                logger.warning("KTown4U returned %d", resp.status_code)
                return []

            if resp.status_code != 200:
                ktown4u_circuit.record_failure()
                logger.warning("KTown4U search returned %d", resp.status_code)
                return []

            ktown4u_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            ktown4u_circuit.record_failure()
            logger.warning("KTown4U search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse KTown4U search results from HTML.

        KTown4U product pages contain:
        - goods_no in product links (e.g., goods_no=12345)
        - Product titles in various elements
        - Prices in KRW (e.g., ₩25,000 or 25,000원)
        - Product images from <img> tags
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract product IDs from links
        product_id_pattern = re.compile(
            r'goods_no=(\d+)',
        )

        # Price pattern — KRW prices like "₩25,000" or "25,000원" or bare numbers
        price_pattern = re.compile(
            r'(?:[₩\u20a9])\s*(\d{1,3}(?:,\d{3})*)|(\d{1,3}(?:,\d{3})*)\s*원',
        )

        # Title pattern — KTown4U uses class with "name" or "title" for product titles
        title_pattern = re.compile(
            r'class="[^"]*(?:goods_name|prd_name|item_name|goods-name|product-name)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern — product images
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*ktown4u[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Broader image pattern — images from CDN or other sources in product listings
        img_pattern_broad = re.compile(
            r'<img[^>]+src="(https?://[^"]*\.(jpg|jpeg|png|webp))"',
            re.IGNORECASE,
        )

        # Extract unique product IDs
        product_ids = list(dict.fromkeys(product_id_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]
        if not images:
            images = [m[0] for m in img_pattern_broad.findall(html)]

        # Extract prices
        price_matches = price_pattern.findall(html)
        prices = []
        for m in price_matches:
            val = m[0] or m[1]
            if val:
                prices.append(val)

        for i, product_id in enumerate(product_ids):
            # Title
            title = titles[i].strip() if i < len(titles) else f"KTown4U product {product_id}"

            # Price
            krw_price = 0.0
            if i < len(prices):
                try:
                    krw_price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # KTown4U items are typically new/sealed
            condition = "New"

            results.append(
                _normalize_listing(product_id, title, krw_price, condition, image_url)
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        KTown4U is a retail storefront and does not expose sold/completed
        order history publicly. Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                KTOWN4U_SEARCH_URL,
                params={"goodsTextSearch": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
