"""
BrickEconomy marketplace adapter for the Marketplace Aggregation Agent.

BrickEconomy (brickeconomy.com) tracks LEGO set values, price history, and
market trends. This adapter scrapes BrickEconomy search results for current
values, retail prices, annual growth percentages, and price history data.

Covers: lego only.

Env vars:
    BRICKECONOMY_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import brickeconomy_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

BRICKECONOMY_SOURCE_RELIABILITY = 0.85
BRICKECONOMY_SOLD_RELIABILITY = 0.90

# BrickEconomy search URL
BRICKECONOMY_SEARCH_URL = "https://www.brickeconomy.com/search"

# BrickEconomy set detail URL pattern
BRICKECONOMY_SET_URL = "https://www.brickeconomy.com/set/{set_number}"

# BrickEconomy only covers LEGO
SUPPORTED_CATEGORIES = ["lego"]


def _parse_price(price_str: str) -> float:
    """Parse a USD price string like '$59.99' or '59.99' into a float."""
    if not price_str:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", price_str)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_listing(
    set_number: str,
    title: str,
    price: float,
    image_url: str,
    url: str,
    retail_price: Optional[float] = None,
    growth_pct: Optional[float] = None,
    is_sold: bool = False,
    sold_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a BrickEconomy listing to the standard MarketHit format."""
    hit: Dict[str, Any] = {
        "source": "brickeconomy",
        "raw_id": f"brickecon-{set_number}",
        "title": title[:500],
        "price": price,
        "currency": "USD",
        "url": url or BRICKECONOMY_SET_URL.format(set_number=set_number),
        "condition": None,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": sold_at,
    }
    # Attach extra valuation metadata
    if retail_price is not None:
        hit["retail_price"] = retail_price
    if growth_pct is not None:
        hit["annual_growth_pct"] = growth_pct
    return hit


class BrickEconomyCaller:
    """Async BrickEconomy adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("BRICKECONOMY_ENABLED", "true").lower() == "true"
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
        """Search BrickEconomy for LEGO set values."""
        if not self.configured:
            return []

        try:
            brickeconomy_circuit.check()
        except CircuitOpenError:
            logger.warning("BrickEconomy circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                BRICKECONOMY_SEARCH_URL,
                params={"query": query},
            )

            if resp.status_code != 200:
                brickeconomy_circuit.record_failure()
                logger.warning("BrickEconomy search returned %d", resp.status_code)
                return []

            brickeconomy_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            brickeconomy_circuit.record_failure()
            logger.warning("BrickEconomy search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse BrickEconomy search results from HTML.

        BrickEconomy's search page contains set cards with:
        - Set number links (e.g. /set/75192-1/millennium-falcon)
        - Set titles/names
        - Current value prices in USD
        - Retail prices in USD
        - Annual growth percentages
        - Set images
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract set links — BrickEconomy uses /set/<number>/<slug>
        set_pattern = re.compile(
            r'href="(/set/(\d{3,6}(?:-\d)?)/([a-zA-Z0-9_-]*))"',
        )

        # Price pattern — USD prices like "$199.99" or "$1,299.99"
        price_pattern = re.compile(
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        )

        # Title pattern — set names in heading or title elements
        title_pattern = re.compile(
            r'class="[^"]*(?:set[_-]?(?:title|name)|card[_-]?title|item[_-]?name|ctitle)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Growth pattern — annual growth like "+12.3%" or "-5.1%"
        growth_pattern = re.compile(
            r'([+-]?\d{1,3}(?:\.\d{1,2})?)\s*%',
        )

        # Image pattern — BrickEconomy / LEGO images
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:brickeconomy|lego|brickset|rebrickable)[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Extract set links (deduplicated)
        set_matches = list(dict.fromkeys(
            [(m[0], m[1], m[2]) for m in set_pattern.findall(html)]
        ))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        growths = growth_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]

        for i, (href, set_number, slug) in enumerate(set_matches):
            # Title
            title = titles[i].strip() if i < len(titles) else f"LEGO {set_number} {slug.replace('-', ' ').title()}"

            # Current value — first price for this item
            price_idx = i * 2  # BrickEconomy typically shows value + retail
            current_value = 0.0
            if price_idx < len(prices):
                current_value = _parse_price(prices[price_idx])

            # Retail price — second price for this item
            retail_price = None
            if price_idx + 1 < len(prices):
                retail_price = _parse_price(prices[price_idx + 1])

            # Growth percentage
            growth_pct = None
            if i < len(growths):
                try:
                    growth_pct = float(growths[i])
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # Full URL
            url = f"https://www.brickeconomy.com{href}" if href.startswith("/") else href

            results.append(
                _normalize_listing(
                    set_number, title, current_value, image_url, url,
                    retail_price=retail_price, growth_pct=growth_pct,
                )
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold/historical price data from BrickEconomy.

        BrickEconomy provides Price History sections with historical market
        values. This scrapes the set detail page for historical data points.
        """
        if not self.configured:
            return []

        try:
            brickeconomy_circuit.check()
        except CircuitOpenError:
            logger.warning("BrickEconomy circuit open — skipping sold_comps")
            return []

        try:
            # First search to find the set page
            client = await self._client()
            resp = await client.get(
                BRICKECONOMY_SEARCH_URL,
                params={"query": query},
            )

            if resp.status_code != 200:
                brickeconomy_circuit.record_failure()
                return []

            brickeconomy_circuit.record_success()

            # Find the first set detail URL
            set_pattern = re.compile(
                r'href="(/set/(\d{3,6}(?:-\d)?)/[^"]*)"',
            )
            match = set_pattern.search(resp.text)
            if not match:
                return []

            set_href = match.group(1)
            set_number = match.group(2)
            detail_url = f"https://www.brickeconomy.com{set_href}"

            # Fetch the detail page for price history
            detail_resp = await client.get(detail_url)
            if detail_resp.status_code != 200:
                return []

            return self._parse_price_history(detail_resp.text, set_number, detail_url, limit)

        except Exception as exc:
            brickeconomy_circuit.record_failure()
            logger.warning("BrickEconomy sold_comps error: %s", exc)
            return []

    def _parse_price_history(
        self, html: str, set_number: str, url: str, limit: int,
    ) -> List[Dict[str, Any]]:
        """Parse BrickEconomy price history from a set detail page.

        Looks for historical price data points with dates and values.
        """
        results: List[Dict[str, Any]] = []

        # Pattern for date+price data points in price history sections
        # BrickEconomy often has data like "Jan 2025 $199.99"
        history_pattern = re.compile(
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\s*[\-:]*\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            re.IGNORECASE,
        )

        # Get the set title from the page
        title_match = re.search(
            r'<h1[^>]*>([^<]+)</h1>',
            html,
        )
        set_title = title_match.group(1).strip() if title_match else f"LEGO {set_number}"

        matches = history_pattern.findall(html)
        for year_str, price_str in matches[:limit]:
            price = _parse_price(price_str)
            if price <= 0:
                continue
            sold_at = f"{year_str}-01-01"
            results.append(
                _normalize_listing(
                    set_number, set_title, price, "", url,
                    is_sold=True, sold_at=sold_at,
                )
            )

        return results

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                BRICKECONOMY_SEARCH_URL,
                params={"query": "lego"},
            )
            return resp.status_code in (200, 403)
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
