"""
KEH Camera marketplace adapter for the Marketplace Aggregation Agent.

KEH (keh.com) is the world's largest used camera dealer with professionally
graded condition pricing. This adapter queries KEH's search API with a
fallback to HTML scraping for active listing prices in USD.

Covers: vintage_cameras only (KEH is a specialist camera retailer).

KEH grades: LN (Like New), EX+ (Excellent Plus), EX (Excellent),
            BGN (Bargain), UG (Ugly)

Env vars:
    KEH_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import keh_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

KEH_SOURCE_RELIABILITY = 0.85

# KEH JSON API endpoint (try first)
KEH_API_URL = "https://www.keh.com/api/catalog/search"

# Fallback: HTML search page
KEH_SEARCH_URL = "https://www.keh.com/shop/catalogsearch/result/"

# KEH only covers vintage cameras
SUPPORTED_CATEGORIES = ["vintage_cameras"]

# KEH condition grade mapping to standard labels
KEH_GRADE_MAP: Dict[str, str] = {
    "LN": "Like New",
    "EX+": "Excellent Plus",
    "EX": "Excellent",
    "BGN": "Bargain",
    "UG": "Ugly",
    "Like New": "Like New",
    "Excellent Plus": "Excellent Plus",
    "Excellent": "Excellent",
    "Bargain": "Bargain",
    "Ugly": "Ugly",
}


def _normalize_grade(grade: Optional[str]) -> Optional[str]:
    """Normalize a KEH grade code/label to a standard condition string."""
    if not grade:
        return None
    cleaned = grade.strip()
    return KEH_GRADE_MAP.get(cleaned, cleaned)


def _normalize_listing(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a KEH listing to the standard MarketHit format."""
    sku = str(item.get("sku") or item.get("id") or item.get("entity_id") or "")
    title = str(item.get("name") or item.get("title") or "Unknown Camera")

    price = 0.0
    for price_field in ("price", "final_price", "special_price", "regular_price"):
        val = item.get(price_field)
        if val is not None:
            try:
                price = float(val)
                if price > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Handle nested price objects
    if price == 0 and isinstance(item.get("price"), dict):
        try:
            price = float(item["price"].get("amount", 0))
        except (ValueError, TypeError):
            pass

    # Condition / Grade
    grade = item.get("grade") or item.get("condition") or item.get("conditionLabel")
    if isinstance(grade, dict):
        grade = grade.get("label") or grade.get("code")
    condition = _normalize_grade(grade)

    # Image URL
    image_url = ""
    if item.get("image_url"):
        image_url = item["image_url"]
    elif item.get("imageUrl"):
        image_url = item["imageUrl"]
    elif item.get("thumbnail"):
        image_url = item["thumbnail"]
    elif item.get("images") and isinstance(item["images"], list):
        first = item["images"][0]
        if isinstance(first, str):
            image_url = first
        elif isinstance(first, dict):
            image_url = first.get("url") or first.get("src") or ""

    # URL
    url_slug = item.get("url_key") or item.get("url") or item.get("slug") or ""
    if url_slug and url_slug.startswith("http"):
        url = url_slug
    elif url_slug:
        url = f"https://www.keh.com/shop/{url_slug}"
    elif sku:
        url = f"https://www.keh.com/shop/catalogsearch/result/?q={quote_plus(sku)}"
    else:
        url = KEH_SEARCH_URL

    return {
        "source": "keh",
        "raw_id": f"keh-{sku}",
        "title": title[:500],
        "price": price,
        "currency": "USD",
        "source_price": price,
        "source_currency": "USD",
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class KEHCaller:
    """Async KEH adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("KEH_ENABLED", "true").lower() == "true"
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
                    "Accept": "application/json, text/html",
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
        """Search KEH for active camera listings."""
        if not self.configured:
            return []

        try:
            keh_circuit.check()
        except CircuitOpenError:
            logger.warning("KEH circuit open -- skipping")
            return []

        try:
            client = await self._client()

            # Try JSON API first
            resp = await client.get(
                KEH_API_URL,
                params={"q": query},
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    items = (
                        data.get("products")
                        or data.get("items")
                        or data.get("results")
                        or data.get("data", [])
                    )
                    if isinstance(data, list):
                        items = data
                    if items:
                        keh_circuit.record_success()
                        return [_normalize_listing(item) for item in items[:limit]]
                except Exception:
                    pass  # Fall through to HTML scrape

            # Fallback to HTML scraping
            logger.debug("KEH API returned %d or empty, attempting page scrape", resp.status_code)
            return await self._scrape_search(query, limit)

        except Exception as exc:
            keh_circuit.record_failure()
            logger.warning("KEH search error: %s", exc)
            return []

    async def _scrape_search(
        self, query: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape KEH search page for listings."""
        try:
            client = await self._client()
            resp = await client.get(
                KEH_SEARCH_URL,
                params={"q": query},
            )
            if resp.status_code != 200:
                keh_circuit.record_failure()
                return []

            keh_circuit.record_success()
            return self._parse_search_page(resp.text, limit)

        except Exception as exc:
            keh_circuit.record_failure()
            logger.warning("KEH scrape error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse KEH search results HTML.

        KEH product pages contain:
        - Product names in title/heading elements
        - Prices in USD (e.g., $599.99)
        - Condition grades (LN, EX+, EX, BGN, UG)
        - Product URLs with /shop/ prefix
        """
        results: List[Dict[str, Any]] = []

        # Product URL pattern — KEH uses /shop/product-slug.html
        product_pattern = re.compile(
            r'/shop/([\w-]+\.html)',
        )

        # Price pattern — USD prices like "$599.99" or "$1,299.00"
        price_pattern = re.compile(
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        )

        # Title pattern — product name in heading or title class
        title_pattern = re.compile(
            r'class="[^"]*(?:product-name|product-item-name|item-name)[^"]*"[^>]*>\s*(?:<a[^>]*>)?\s*([^<]+)',
            re.IGNORECASE,
        )

        # Grade pattern — KEH grades in parentheses or separate labels
        grade_pattern = re.compile(
            r'\b(LN|EX\+|EX|BGN|UG|Like New|Excellent Plus|Excellent|Bargain|Ugly)\b',
            re.IGNORECASE,
        )

        # Image pattern
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*keh[^"]*\.(?:jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        product_slugs = list(dict.fromkeys(product_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        grades = grade_pattern.findall(html)
        images = img_pattern.findall(html)

        for i, slug in enumerate(product_slugs):
            title = titles[i].strip() if i < len(titles) else f"KEH item {slug}"

            price = 0.0
            if i < len(prices):
                try:
                    price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            condition = _normalize_grade(grades[i]) if i < len(grades) else None
            image_url = images[i] if i < len(images) else ""

            results.append({
                "source": "keh",
                "raw_id": f"keh-{slug}",
                "title": title[:500],
                "price": price,
                "currency": "USD",
                "source_price": price,
                "source_currency": "USD",
                "url": f"https://www.keh.com/shop/{slug}",
                "condition": condition,
                "image_url": image_url,
                "is_sold": False,
                "sold_at": None,
            })

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        KEH does not expose sold history publicly -- all items on their
        site are current active listings with fixed pricing. Returns an
        empty list.
        """
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                KEH_API_URL,
                params={"q": "leica"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
