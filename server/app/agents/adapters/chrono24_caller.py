"""
Chrono24 marketplace adapter for the Marketplace Aggregation Agent.

Chrono24 is the world's largest watch marketplace. This adapter scrapes
Chrono24 search results for active and sold watch listings.

IMPORTANT: Chrono24 prices can be unreliable/inflated. A cross-reference
method compares Chrono24 prices against existing market_hits median for
the same item. If the price deviates >40% from median, reliability is
degraded from 0.70 to 0.55.

Covers: watches only (Chrono24 is a specialist watch marketplace).

Env vars:
    CHRONO24_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
import statistics
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import chrono24_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

CHRONO24_SOURCE_RELIABILITY = 0.70
CHRONO24_SOLD_RELIABILITY = 0.75
CHRONO24_DEGRADED_RELIABILITY = 0.55

# Price deviation threshold for cross-reference degradation
PRICE_DEVIATION_THRESHOLD = 0.40

# Chrono24 search URL
CHRONO24_SEARCH_URL = "https://www.chrono24.com/search/index.htm"

# Chrono24 only covers watches
SUPPORTED_CATEGORIES = ["watches"]


def _normalize_listing(item: Dict[str, Any], is_sold: bool = False) -> Dict[str, Any]:
    """Normalize a Chrono24 listing to the standard MarketHit format."""
    item_id = item.get("id") or item.get("articleId") or item.get("listingId") or ""

    title_parts = []
    if item.get("manufacturer"):
        title_parts.append(item["manufacturer"])
    elif item.get("brand"):
        title_parts.append(item["brand"])
    if item.get("model"):
        title_parts.append(item["model"])
    if item.get("referenceNumber"):
        title_parts.append(f"Ref. {item['referenceNumber']}")
    title = " ".join(title_parts) if title_parts else item.get("title") or item.get("name") or "Unknown Watch"

    price = 0.0
    currency = "EUR"  # Chrono24 is EUR-based by default

    for price_field in ("price", "priceValue", "askPrice", "soldPrice", "listPrice"):
        val = item.get(price_field)
        if val:
            try:
                price = float(val)
                if price > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Handle nested price objects (e.g. {"value": 5000, "currency": "EUR"})
    if price == 0 and isinstance(item.get("price"), dict):
        try:
            price = float(item["price"].get("value") or item["price"].get("amount", 0))
            currency = item["price"].get("currency", "EUR")
        except (ValueError, TypeError):
            pass

    # Currency from item
    if item.get("currency"):
        currency = item["currency"]
    elif item.get("priceCurrency"):
        currency = item["priceCurrency"]

    # Image URL
    image_url = ""
    if item.get("imageUrl"):
        image_url = item["imageUrl"]
    elif item.get("image"):
        img = item["image"]
        if isinstance(img, str):
            image_url = img
        elif isinstance(img, dict):
            image_url = img.get("url") or img.get("src") or ""
    elif item.get("images") and isinstance(item["images"], list):
        first = item["images"][0]
        if isinstance(first, str):
            image_url = first
        elif isinstance(first, dict):
            image_url = first.get("url") or first.get("src") or ""

    # Condition
    condition = item.get("condition") or item.get("conditionLabel")
    if isinstance(condition, dict):
        condition = condition.get("label") or condition.get("name")

    # URL
    slug = item.get("slug") or item.get("url") or ""
    if slug and slug.startswith("http"):
        url = slug
    elif slug:
        url = f"https://www.chrono24.com{slug}" if slug.startswith("/") else f"https://www.chrono24.com/{slug}"
    elif item_id:
        url = f"https://www.chrono24.com/id{item_id}.htm"
    else:
        url = CHRONO24_SEARCH_URL

    # Location / dealer info
    location = item.get("location") or item.get("merchantLocation") or item.get("country")

    # Per-listing attributes — watch specifics that drive price variance
    listing_attrs: Dict[str, Any] = {}
    if condition:
        listing_attrs["condition"] = condition
    if item.get("manufacturer") or item.get("brand"):
        listing_attrs["brand"] = item.get("manufacturer") or item.get("brand")
    if item.get("model"):
        listing_attrs["model"] = item["model"]
    if item.get("referenceNumber") or item.get("reference_number"):
        listing_attrs["reference_number"] = item.get("referenceNumber") or item.get("reference_number")
    if item.get("movement"):
        listing_attrs["movement"] = item["movement"]
    if item.get("caseMaterial") or item.get("case_material"):
        listing_attrs["case_material"] = item.get("caseMaterial") or item.get("case_material")
    if item.get("year"):
        listing_attrs["year"] = item["year"]
    if location:
        listing_attrs["country"] = location

    return {
        "source": "chrono24",
        "raw_id": f"chrono24-{item_id}",
        "title": str(title)[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": item.get("soldAt") or item.get("soldDate") or item.get("endDate") if is_sold else None,
        "attributes": listing_attrs,
    }


class Chrono24Caller:
    """Async Chrono24 adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("CHRONO24_ENABLED", "true").lower() == "true"
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
                    "Accept": "text/html, application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
        return self._http

    def _cross_reference_price(
        self,
        hits: List[Dict[str, Any]],
        existing_hits: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Compare Chrono24 prices against existing market_hits median.

        If a Chrono24 price deviates >40% from the median of other sources,
        flag the hit with degraded reliability by adding a
        ``_reliability_override`` field.

        Parameters
        ----------
        hits:
            Normalized Chrono24 MarketHit dicts to evaluate.
        existing_hits:
            Optional list of MarketHit dicts from other sources for the same
            item. When provided, prices from these hits are used to compute
            the reference median.

        Returns
        -------
        The *hits* list (mutated in place) with ``_reliability_override``
        added to any hit whose price deviates significantly.
        """
        if not existing_hits:
            return hits

        # Compute median from other sources (only positive prices)
        other_prices = [
            h.get("price", 0)
            for h in existing_hits
            if h.get("source") != "chrono24" and h.get("price", 0) > 0
        ]
        if not other_prices:
            return hits

        median_price = statistics.median(other_prices)
        if median_price <= 0:
            return hits

        for hit in hits:
            hp = hit.get("price", 0)
            if hp <= 0:
                continue
            deviation = abs(hp - median_price) / median_price
            if deviation > PRICE_DEVIATION_THRESHOLD:
                hit["_reliability_override"] = CHRONO24_DEGRADED_RELIABILITY
                logger.info(
                    "Chrono24 price $%.2f deviates %.0f%% from median $%.2f -- degrading reliability to %.2f",
                    hp, deviation * 100, median_price, CHRONO24_DEGRADED_RELIABILITY,
                )

        return hits

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        existing_hits: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Search Chrono24 for active watch listings."""
        if not self.configured:
            return []

        try:
            chrono24_circuit.check()
        except CircuitOpenError:
            logger.warning("Chrono24 circuit open -- skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                CHRONO24_SEARCH_URL,
                params={
                    "query": query,
                    "dosearch": "true",
                    "maxAgeInDays": "0",  # active listings only
                },
            )

            if resp.status_code == 200:
                # Try to extract JSON data from page (Chrono24 embeds structured data)
                hits = self._parse_search_page(resp.text, query, limit, is_sold=False)
                chrono24_circuit.record_success()
                return self._cross_reference_price(hits, existing_hits)

            chrono24_circuit.record_failure()
            logger.debug("Chrono24 returned %d for search", resp.status_code)
            return []

        except Exception as exc:
            chrono24_circuit.record_failure()
            logger.warning("Chrono24 search error: %s", exc)
            return []

    def _parse_search_page(
        self, html: str, query: str, limit: int, is_sold: bool = False
    ) -> List[Dict[str, Any]]:
        """Parse Chrono24 search results from HTML.

        Chrono24 embeds structured data and listing info in the page.
        We extract listing IDs, prices, and titles from the HTML.
        """
        results = []

        # Extract listing IDs from URLs
        listing_pattern = re.compile(r'/id(\d+)\.htm')
        # Also try article-id data attributes
        article_pattern = re.compile(r'data-article-id="(\d+)"')

        ids_from_urls = listing_pattern.findall(html)
        ids_from_attrs = article_pattern.findall(html)
        all_ids = list(dict.fromkeys(ids_from_urls + ids_from_attrs))[:limit]

        # Extract prices — Chrono24 uses various price formats
        price_patterns = [
            re.compile(r'data-price="(\d+(?:\.\d+)?)"'),
            re.compile(r'class="[^"]*price[^"]*"[^>]*>\s*[^\d]*(\d{1,3}(?:[,.]?\d{3})*(?:\.\d{2})?)\s*(?:EUR|USD|GBP)', re.IGNORECASE),
            re.compile(r'[\$\u20ac\xa3]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'),
        ]

        prices: List[float] = []
        for pp in price_patterns:
            found = pp.findall(html)
            if found:
                for p in found:
                    try:
                        prices.append(float(p.replace(",", "")))
                    except ValueError:
                        continue
                break  # Use first pattern that matches

        # Extract titles from the page
        title_pattern = re.compile(
            r'<(?:h[23]|a)[^>]*class="[^"]*(?:article-title|listing-title|watch-title)[^"]*"[^>]*>([^<]+)</(?:h[23]|a)>',
            re.IGNORECASE,
        )
        titles = [t.strip() for t in title_pattern.findall(html) if t.strip()]

        for i, listing_id in enumerate(all_ids):
            price = prices[i] if i < len(prices) else 0.0
            title = titles[i] if i < len(titles) else query

            results.append({
                "source": "chrono24",
                "raw_id": f"chrono24-{listing_id}",
                "title": str(title)[:500],
                "price": price,
                "currency": "EUR",
                "source_price": price,
                "source_currency": "EUR",
                "url": f"https://www.chrono24.com/id{listing_id}.htm",
                "condition": None,
                "image_url": "",
                "is_sold": is_sold,
                "sold_at": None,
            })

        return results[:limit]

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        existing_hits: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Search Chrono24 for sold/completed watch listings."""
        if not self.configured:
            return []

        try:
            chrono24_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            # Chrono24 sold listings use a "sold" filter
            resp = await client.get(
                CHRONO24_SEARCH_URL,
                params={
                    "query": query,
                    "dosearch": "true",
                    "soldItems": "true",
                },
            )

            if resp.status_code == 200:
                hits = self._parse_search_page(resp.text, query, limit, is_sold=True)
                chrono24_circuit.record_success()
                return self._cross_reference_price(hits, existing_hits)

            # 2026-04-23 silent-failure sweep: never record success on non-200.
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                chrono24_circuit.record_failure()
                logger.warning("Chrono24 sold_comps HTTP %d — circuit failure", resp.status_code)
            return []

        except Exception as exc:
            chrono24_circuit.record_failure()
            logger.warning("Chrono24 sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                CHRONO24_SEARCH_URL,
                params={"query": "rolex", "dosearch": "true"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
