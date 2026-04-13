"""
Gumtree marketplace adapter for the Marketplace Aggregation Agent.

Gumtree is the UK's largest classifieds platform, widely used for
second-hand collectibles, vintage items, and electronics.
Scrapes the public search page via httpx.

Primary region: United Kingdom
Prices in GBP.

Env vars:
    GUMTREE_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import gumtree_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

GUMTREE_SOURCE_RELIABILITY = 0.55
GUMTREE_SOLD_RELIABILITY = 0.40  # Gumtree doesn't clearly indicate sold items

GUMTREE_SEARCH_URL = "https://www.gumtree.com/search"
GUMTREE_ENABLED = os.getenv("GUMTREE_ENABLED", "true").lower() in ("true", "1", "yes")

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _parse_price(text: str) -> tuple[float, str]:
    """Extract numeric price and currency from a price string like '£45.00'."""
    text = text.strip()
    if text.startswith("£"):
        num = re.sub(r"[^\d.]", "", text)
        return (float(num), "GBP") if num else (0.0, "GBP")
    if text.startswith("$"):
        num = re.sub(r"[^\d.]", "", text)
        return (float(num), "USD") if num else (0.0, "USD")
    num = re.sub(r"[^\d.]", "", text)
    return (float(num), "GBP") if num else (0.0, "GBP")


class GumtreeCaller:
    """Gumtree UK search adapter."""

    source_name = "gumtree"

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
        return GUMTREE_ENABLED

    async def search(
        self,
        query: str,
        limit: int = 20,
        region: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search Gumtree for active listings."""
        if not self.configured():
            return []

        try:
            gumtree_circuit.check()
        except CircuitOpenError:
            logger.warning("Gumtree circuit open — skipping")
            return []

        client = await self._get_client()
        params = {
            "search_category": "all",
            "q": query,
            "search_location": "UK",
        }

        try:
            resp = await client.get(GUMTREE_SEARCH_URL, params=params)
            resp.raise_for_status()
            gumtree_circuit.record_success()
        except Exception as e:
            gumtree_circuit.record_failure()
            logger.error("[Gumtree] Search failed: %s", e)
            return []

        return self._parse_listings(resp.text, limit)

    async def sold_comps(
        self,
        query: str,
        limit: int = 20,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Gumtree doesn't expose sold listings."""
        return []

    def _parse_listings(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Gumtree search results from HTML."""
        results: List[Dict[str, Any]] = []

        # Gumtree uses data in listing cards — extract via regex patterns
        # Pattern: article blocks with listing data
        listing_blocks = re.findall(
            r'<article[^>]*data-q="(?:search-result|listing)"[^>]*>(.*?)</article>',
            html,
            re.DOTALL,
        )

        if not listing_blocks:
            # Fallback: try JSON-LD or script tag data
            json_match = re.search(
                r'"listing":\s*\[(.*?)\]',
                html,
                re.DOTALL,
            )
            if json_match:
                import json
                try:
                    listings = json.loads(f"[{json_match.group(1)}]")
                    for item in listings[:limit]:
                        results.append(self._normalize_json_item(item))
                    return results
                except (json.JSONDecodeError, KeyError):
                    pass

        for block in listing_blocks[:limit]:
            try:
                # Extract title
                title_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

                # Extract price
                price_match = re.search(r'<span[^>]*class="[^"]*price[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
                price_text = re.sub(r'<[^>]+>', '', price_match.group(1)).strip() if price_match else "0"
                price, currency = _parse_price(price_text)

                # Extract URL
                url_match = re.search(r'href="(/[^"]+)"', block)
                url = f"https://www.gumtree.com{url_match.group(1)}" if url_match else ""

                # Extract image
                img_match = re.search(r'src="(https://[^"]+\.(?:jpg|jpeg|png|webp))"', block, re.IGNORECASE)
                image_url = img_match.group(1) if img_match else ""

                # Extract listing ID from URL
                listing_id = ""
                if url:
                    id_match = re.search(r'/(\d+)$', url)
                    listing_id = f"gumtree-{id_match.group(1)}" if id_match else url[-20:]

                if title and price > 0:
                    results.append({
                        "source": "gumtree",
                        "raw_id": listing_id,
                        "title": title,
                        "price": price,
                        "currency": currency,
                        "url": url,
                        "image_url": image_url,
                        "condition": None,
                        "is_sold": False,
                    })
            except Exception as e:
                logger.debug("[Gumtree] Failed to parse listing: %s", e)
                continue

        return results

    def _normalize_json_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a JSON listing object."""
        price_text = str(item.get("price", "0"))
        price, currency = _parse_price(price_text)
        return {
            "source": "gumtree",
            "raw_id": f"gumtree-{item.get('id', '')}",
            "title": item.get("title", ""),
            "price": price,
            "currency": currency,
            "url": item.get("url", ""),
            "image_url": item.get("imageUrl", ""),
            "condition": None,
            "is_sold": False,
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "source": "gumtree",
            "configured": self.configured(),
            "circuit_closed": not gumtree_circuit.is_open(),
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
