"""
ScaleMates marketplace adapter for the Marketplace Aggregation Agent.

ScaleMates (scalemates.com) is the definitive scale model database with
community-sourced market values, covering model kits, diecast, and gunpla.
This adapter scrapes ScaleMates search results to extract listing/reference
prices, typically in EUR or USD.

Covers collectible categories: scale_models, gunpla, diecast.

Env vars:
    SCALEMATES_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import scalemates_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

SCALEMATES_SOURCE_RELIABILITY = 0.75

# ScaleMates search URL (Kits section)
SCALEMATES_SEARCH_URL = "https://www.scalemates.com/search.php"

# ScaleMates kit detail URL prefix
SCALEMATES_DETAIL_URL = "https://www.scalemates.com/kits"

# Categories that ScaleMates excels in
SUPPORTED_CATEGORIES = [
    "scale_models",
    "gunpla",
    "diecast",
]

# USD to EUR fallback rate (used when import_common is unavailable)
_FALLBACK_USD_TO_EUR = 0.92


def _convert_to_eur(price: float, currency: str) -> float:
    """Convert price to EUR using live rates with fallback."""
    if currency == "EUR":
        return price
    try:
        from pipelines.import_common import to_eur
        return to_eur(price, currency)
    except Exception:
        if currency == "USD":
            return round(price * _FALLBACK_USD_TO_EUR, 2)
        return price  # Return as-is if no conversion available


def _parse_price(price_str: str) -> tuple[float, str]:
    """Parse a price string like '$12.99', '€15.50', or '¥3,500' into (value, currency).

    Returns (price, currency_code) where currency_code is EUR, USD, or GBP.
    """
    if not price_str:
        return 0.0, "EUR"

    # Detect currency from symbol
    currency = "EUR"  # default
    if "$" in price_str:
        currency = "USD"
    elif "£" in price_str:
        currency = "GBP"
    elif "€" in price_str:
        currency = "EUR"

    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[$¥€£,\s]", "", price_str)
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned), currency
    except (ValueError, TypeError):
        return 0.0, currency


def _normalize_listing(
    kit_id: str,
    title: str,
    price: float,
    source_currency: str,
    condition: Optional[str],
    image_url: str,
    scale: Optional[str] = None,
    manufacturer: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a ScaleMates listing to the standard MarketHit format."""
    eur_price = _convert_to_eur(price, source_currency)
    item_url = f"{SCALEMATES_DETAIL_URL}/{kit_id}" if kit_id else SCALEMATES_SEARCH_URL

    title_full = title
    if scale:
        title_full = f"[{scale}] {title}"
    if manufacturer:
        title_full = f"{title_full} ({manufacturer})"

    return {
        "source": "scalemates",
        "raw_id": f"scalemates-{kit_id}",
        "title": title_full[:500],
        "price": eur_price,
        "currency": "EUR",
        "source_price": price,
        "source_currency": source_currency,
        "url": item_url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class ScaleMatesCaller:
    """Async ScaleMates adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("SCALEMATES_ENABLED", "true").lower() == "true"
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
                    "Accept-Language": "en-US,en;q=0.9",
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
        """Search ScaleMates for model kits and pricing data."""
        if not self.configured:
            return []

        try:
            scalemates_circuit.check()
        except CircuitOpenError:
            logger.warning("ScaleMates circuit open — skipping")
            return []

        try:
            client = await self._client()
            params: Dict[str, str] = {
                "q": query,
            }
            # Restrict to Kits section for focused results
            if category in ("scale_models", "gunpla"):
                params["fkSECTION[]"] = "Kits"

            resp = await client.get(
                SCALEMATES_SEARCH_URL,
                params=params,
            )

            if resp.status_code != 200:
                scalemates_circuit.record_failure()
                logger.warning("ScaleMates search returned %d", resp.status_code)
                return []

            scalemates_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            scalemates_circuit.record_failure()
            logger.warning("ScaleMates search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse ScaleMates search results from HTML.

        ScaleMates search results contain kit entries with:
        - Kit IDs in links (e.g., /kits/brand-name--kit-id)
        - Kit titles and manufacturer names
        - Scale information (e.g., 1:72, 1:48)
        - Market value / price references
        - Box art images
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract kit IDs from links — ScaleMates uses /kits/SLUG--ID
        kit_id_pattern = re.compile(
            r'/kits/([a-zA-Z0-9_-]+--[a-zA-Z0-9_-]+)',
        )

        # Price pattern — prices like "$12.99", "€15.50", "£9.99"
        price_pattern = re.compile(
            r'([$€£])\s*(\d{1,4}(?:[.,]\d{1,2})?)',
        )

        # Title pattern — ScaleMates uses title/product-name classes
        title_pattern = re.compile(
            r'class="[^"]*(?:product-name|kit-name|result-title|title)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Scale pattern — e.g., "1:72", "1/48", "1:35"
        scale_pattern = re.compile(
            r'(1[:/]\d{1,4})',
        )

        # Manufacturer pattern
        manufacturer_pattern = re.compile(
            r'class="[^"]*(?:manufacturer|brand|maker)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern — ScaleMates image URLs
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:scalemates|s\.scalemates)[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Extract unique kit IDs
        kit_ids = list(dict.fromkeys(kit_id_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        price_matches = price_pattern.findall(html)
        scales = scale_pattern.findall(html)
        manufacturers = manufacturer_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        # Currency symbol to code mapping
        symbol_to_code = {"$": "USD", "€": "EUR", "£": "GBP"}

        for i, kit_id in enumerate(kit_ids):
            # Title
            title = titles[i].strip() if i < len(titles) else f"ScaleMates kit {kit_id}"

            # Price
            price = 0.0
            source_currency = "EUR"
            if i < len(price_matches):
                symbol, price_str = price_matches[i]
                source_currency = symbol_to_code.get(symbol, "EUR")
                try:
                    price = float(price_str.replace(",", "."))
                except (ValueError, TypeError):
                    pass

            # Scale
            scale = scales[i] if i < len(scales) else None

            # Manufacturer
            manufacturer = manufacturers[i].strip() if i < len(manufacturers) else None

            # Image
            image_url = images[i] if i < len(images) else ""

            # ScaleMates items are reference/database listings — condition is typically New (kits)
            condition = "New"

            results.append(
                _normalize_listing(
                    kit_id, title, price, source_currency,
                    condition, image_url, scale, manufacturer,
                )
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        ScaleMates is a database/reference site — it does not track
        individual sold transactions. Returns an empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                SCALEMATES_SEARCH_URL,
                params={"q": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
