"""
130point.com marketplace adapter for the Marketplace Aggregation Agent.

130point.com aggregates eBay sold data specifically for sports cards
(baseball, basketball, football, hockey). Also covers Pokemon cards.
Scrapes the public search results page via httpx — no API key needed.

Prices in USD.

Env vars:
    ONETWOTHIRTYPOINT_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import onetwothirtypoint_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

ONETWOTHIRTYPOINT_SOURCE_RELIABILITY = 0.80
ONETWOTHIRTYPOINT_SOLD_RELIABILITY = 0.80  # all data is sold comps

SEARCH_URL = "https://130point.com/sales/"
ONETWOTHIRTYPOINT_ENABLED = os.getenv(
    "ONETWOTHIRTYPOINT_ENABLED", "true"
).lower() in ("true", "1", "yes")

SUPPORTED_CATEGORIES = frozenset([
    "sportscards",
    "pokemon",
    "retro_pokemon",
])

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _parse_price(text: str) -> float | None:
    """Extract numeric USD price from text like '$45.00' or '45.00'."""
    text = text.strip().replace(",", "")
    match = re.search(r"\$?([\d]+(?:\.[\d]{1,2})?)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_date(text: str) -> str | None:
    """Parse date string from 130point table into ISO format.

    Common formats: 'Apr 10, 2026', '04/10/2026', '2026-04-10'.
    """
    text = text.strip()
    if not text:
        return None

    # ISO format already
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    for fmt in ("%b %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


class OneTwoThirtyPointCaller:
    """130point.com sold-price search adapter."""

    source_name = "130point"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            )
        return self._client

    def configured(self) -> bool:
        return ONETWOTHIRTYPOINT_ENABLED

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search 130point for recent sold listings (active-equivalent).

        130point only has sold data, so search() returns recent sales.
        """
        return await self._fetch_sales(query, category, limit)

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Fetch sold comps — same endpoint since all data is sold."""
        return await self._fetch_sales(query, category, limit)

    async def _fetch_sales(
        self,
        query: str,
        category: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Core fetch: hit the 130point search page and parse results."""
        if not self.configured():
            return []

        if category and category not in SUPPORTED_CATEGORIES:
            logger.debug(
                "[130point] category %s not supported — skipping", category
            )
            return []

        try:
            onetwothirtypoint_circuit.check()
        except CircuitOpenError:
            logger.warning("[130point] circuit open — skipping")
            return []

        client = await self._get_client()

        try:
            resp = await client.get(
                SEARCH_URL,
                params={"search": query},
            )
            resp.raise_for_status()
            onetwothirtypoint_circuit.record_success()
        except Exception as e:
            onetwothirtypoint_circuit.record_failure()
            logger.error("[130point] Search failed: %s", e)
            return []

        return self._parse_table(resp.text, limit)

    def _parse_table(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse the sold-items table from 130point HTML.

        The table has columns: Date, Card, Set, #, Grade, Price.
        Rows are inside <tr> tags within the results table.
        """
        results: List[Dict[str, Any]] = []

        # Find the results table — look for table rows with sold data
        # 130point uses a table with class or id for results
        table_match = re.search(
            r'<table[^>]*id="[^"]*sales[^"]*"[^>]*>(.*?)</table>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not table_match:
            # Fallback: find any table that has price-like data
            table_match = re.search(
                r'<table[^>]*>(.*?)</table>',
                html,
                re.DOTALL | re.IGNORECASE,
            )

        if not table_match:
            logger.debug("[130point] No table found in HTML")
            return []

        table_html = table_match.group(1)

        # Extract all rows (skip header row)
        rows = re.findall(
            r"<tr[^>]*>(.*?)</tr>",
            table_html,
            re.DOTALL | re.IGNORECASE,
        )

        for row in rows:
            if len(results) >= limit:
                break

            # Extract cells — both <td> and <th>
            cells = re.findall(
                r"<t[dh][^>]*>(.*?)</t[dh]>",
                row,
                re.DOTALL | re.IGNORECASE,
            )

            if len(cells) < 4:
                continue

            # Skip header rows
            if any("date" in _clean_html(c).lower() for c in cells[:2]):
                continue

            try:
                parsed = self._parse_row(cells)
                if parsed and parsed.get("price") is not None and parsed["price"] > 0:
                    results.append(parsed)
            except Exception as e:
                logger.debug("[130point] Failed to parse row: %s", e)
                continue

        return results

    def _parse_row(self, cells: List[str]) -> Dict[str, Any] | None:
        """Parse a single table row into a MarketHit dict.

        Expected column order: Date, Card, Set, #, Grade, Price
        Some rows may have fewer columns; we handle 4-6 gracefully.
        """
        cleaned = [_clean_html(c) for c in cells]

        # Extract URL from the card name cell (usually cell index 1)
        card_url = ""
        for cell in cells[:3]:
            url_match = re.search(r'href="([^"]+)"', cell)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = f"https://130point.com{url}"
                card_url = url
                break

        # Map columns based on count
        if len(cleaned) >= 6:
            date_str, card_name, set_name, card_number, grade, price_str = (
                cleaned[0], cleaned[1], cleaned[2],
                cleaned[3], cleaned[4], cleaned[5],
            )
        elif len(cleaned) == 5:
            date_str, card_name, set_name, card_number, price_str = (
                cleaned[0], cleaned[1], cleaned[2], cleaned[3], cleaned[4],
            )
            grade = None
        elif len(cleaned) == 4:
            date_str, card_name, price_str = cleaned[0], cleaned[1], cleaned[-1]
            set_name = cleaned[2] if len(cleaned) > 2 else ""
            card_number = ""
            grade = None
        else:
            return None

        price = _parse_price(price_str)
        if price is None:
            return None

        # Build title from card name + set + number + grade
        title_parts = [card_name]
        if set_name:
            title_parts.append(set_name)
        if card_number:
            title_parts.append(f"#{card_number}")
        if grade:
            title_parts.append(grade)
        title = " - ".join(p for p in title_parts if p)

        sold_date = _parse_date(date_str)

        # Generate a stable raw_id from title + date + price
        raw_id = f"130point-{hash(f'{title}{sold_date}{price}') & 0xFFFFFFFF:08x}"

        return {
            "source": "130point",
            "raw_id": raw_id,
            "title": title[:500],
            "price": price,
            "currency": "USD",
            "source_price": price,
            "source_currency": "USD",
            "sold_at": sold_date,
            "url": card_url or "https://130point.com/sales/",
            "image_url": "",
            "condition": grade,
            "is_sold": True,
            "card_number": card_number if card_number else None,
            "set_name": set_name if set_name else None,
            "grade": grade if grade else None,
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "source": "130point",
            "configured": self.configured(),
            "circuit_closed": not onetwothirtypoint_circuit.is_open(),
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
