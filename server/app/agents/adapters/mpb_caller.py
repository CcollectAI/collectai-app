"""
MPB marketplace adapter for the Marketplace Aggregation Agent.

MPB (mpb.com) is a major used camera and lens marketplace operating in the
US and Europe. This adapter scrapes MPB search results for active listing
prices in USD (US site) or GBP (UK site).

Covers: vintage_cameras only (MPB is a specialist camera/lens marketplace).

MPB grades: Like New, Excellent, Good, Well Used, Heavily Used

Env vars:
    MPB_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import mpb_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

MPB_SOURCE_RELIABILITY = 0.80

# MPB search URL (US site)
MPB_SEARCH_URL = "https://www.mpb.com/en-us/search"

# MPB UK search URL (alternative for European region)
MPB_UK_SEARCH_URL = "https://www.mpb.com/en-uk/search"

# MPB only covers cameras/lenses
SUPPORTED_CATEGORIES = ["vintage_cameras"]

# MPB condition grade mapping to standard labels
MPB_GRADE_MAP: Dict[str, str] = {
    "Like New": "Like New",
    "Excellent": "Excellent",
    "Good": "Good",
    "Well Used": "Well Used",
    "Heavily Used": "Heavily Used",
    "like new": "Like New",
    "excellent": "Excellent",
    "good": "Good",
    "well used": "Well Used",
    "heavily used": "Heavily Used",
}


def _normalize_grade(grade: Optional[str]) -> Optional[str]:
    """Normalize an MPB grade label to a standard condition string."""
    if not grade:
        return None
    cleaned = grade.strip()
    return MPB_GRADE_MAP.get(cleaned, MPB_GRADE_MAP.get(cleaned.lower(), cleaned))


def _normalize_listing(
    item: Dict[str, Any],
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize an MPB listing to the standard MarketHit format."""
    product_id = str(item.get("id") or item.get("productId") or item.get("slug") or "")
    title = str(item.get("name") or item.get("title") or "Unknown Camera")

    price = 0.0
    for price_field in ("price", "salePrice", "displayPrice", "listPrice"):
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

    # Currency depends on region
    is_uk = region == "europe"
    currency = "GBP" if is_uk else "USD"

    # Condition / Grade
    grade = item.get("condition") or item.get("grade") or item.get("conditionLabel")
    if isinstance(grade, dict):
        grade = grade.get("label") or grade.get("name")
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
    slug = item.get("slug") or item.get("url") or item.get("permalink") or ""
    base_url = "https://www.mpb.com/en-uk" if is_uk else "https://www.mpb.com/en-us"
    if slug and slug.startswith("http"):
        url = slug
    elif slug:
        url = f"{base_url}/product/{slug}"
    elif product_id:
        url = f"{base_url}/product/{product_id}"
    else:
        url = f"{base_url}/search"

    return {
        "source": "mpb",
        "raw_id": f"mpb-{product_id}",
        "title": title[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class MPBCaller:
    """Async MPB adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("MPB_ENABLED", "true").lower() == "true"
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
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search MPB for active camera/lens listings."""
        if not self.configured:
            return []

        try:
            mpb_circuit.check()
        except CircuitOpenError:
            logger.warning("MPB circuit open -- skipping")
            return []

        is_uk = region == "europe"
        search_url = MPB_UK_SEARCH_URL if is_uk else MPB_SEARCH_URL

        try:
            client = await self._client()
            resp = await client.get(
                search_url,
                params={"q": query},
            )

            if resp.status_code != 200:
                mpb_circuit.record_failure()
                logger.warning("MPB search returned %d", resp.status_code)
                return []

            mpb_circuit.record_success()
            return self._parse_search_page(resp.text, limit, region)

        except Exception as exc:
            mpb_circuit.record_failure()
            logger.warning("MPB search error: %s", exc)
            return []

    def _parse_search_page(
        self, html: str, limit: int, region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Parse MPB search results HTML.

        MPB product pages contain:
        - Product names in heading/link elements
        - Prices in USD ($) or GBP (pound)
        - Condition grades (Like New, Excellent, Good, Well Used, Heavily Used)
        - Product URLs with /product/ prefix
        """
        results: List[Dict[str, Any]] = []

        is_uk = region == "europe"
        currency = "GBP" if is_uk else "USD"

        # Product URL pattern — MPB uses /product/slug or /en-us/product/slug
        product_pattern = re.compile(
            r'/(?:en-(?:us|uk)/)?product/([\w-]+)',
        )

        # Price patterns — USD ($999.00) or GBP (£999.00)
        price_pattern = re.compile(
            r'[\$\u00a3](\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        )

        # Title pattern — product name in heading or product-card title
        title_pattern = re.compile(
            r'class="[^"]*(?:product-name|product-card__title|product-title|item-name)[^"]*"[^>]*>\s*(?:<a[^>]*>)?\s*([^<]+)',
            re.IGNORECASE,
        )

        # Condition pattern — MPB grade labels
        condition_pattern = re.compile(
            r'\b(Like New|Excellent|Good|Well Used|Heavily Used)\b',
            re.IGNORECASE,
        )

        # Image pattern
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*mpb[^"]*\.(?:jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        product_slugs = list(dict.fromkeys(product_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        prices = price_pattern.findall(html)
        conditions = condition_pattern.findall(html)
        images = img_pattern.findall(html)

        base_url = "https://www.mpb.com/en-uk" if is_uk else "https://www.mpb.com/en-us"

        for i, slug in enumerate(product_slugs):
            title = titles[i].strip() if i < len(titles) else f"MPB item {slug}"

            price = 0.0
            if i < len(prices):
                try:
                    price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            condition = _normalize_grade(conditions[i]) if i < len(conditions) else None
            image_url = images[i] if i < len(images) else ""

            results.append({
                "source": "mpb",
                "raw_id": f"mpb-{slug}",
                "title": title[:500],
                "price": price,
                "currency": currency,
                "source_price": price,
                "source_currency": currency,
                "url": f"{base_url}/product/{slug}",
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
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return sold comparables.

        MPB does not expose sold history publicly -- all items on their
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
                MPB_SEARCH_URL,
                params={"q": "leica"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
