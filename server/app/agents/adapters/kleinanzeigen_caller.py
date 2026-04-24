"""
Kleinanzeigen marketplace adapter for the Marketplace Aggregation Agent.

Kleinanzeigen (formerly eBay Kleinanzeigen) is Germany's largest classifieds
platform with 50M+ monthly users.  No API key required.

Primary strategy: JSON API at api.kleinanzeigen.de.
Fallback: HTML scrape of the public search page.

Primary region: Germany
Prices in EUR.

Env vars:
    KLEINANZEIGEN_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import kleinanzeigen_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

KLEINANZEIGEN_SOURCE_RELIABILITY = 0.65

# JSON API endpoint (public, no key required)
KLEINANZEIGEN_API_URL = "https://api.kleinanzeigen.de/api/ads.json"

# HTML fallback search URL
KLEINANZEIGEN_HTML_URL = "https://www.kleinanzeigen.de/s-{query}/k0"

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def _normalize_api_ad(ad: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Kleinanzeigen JSON API ad to the standard MarketHit format."""
    ad_id = ad.get("id") or ""
    title = ad.get("title") or "Unknown"

    # Price
    price = 0.0
    currency = "EUR"
    price_obj = ad.get("price") or {}
    if isinstance(price_obj, dict):
        raw_amount = price_obj.get("amount")
        if raw_amount is not None:
            try:
                price = float(raw_amount)
            except (ValueError, TypeError):
                pass
        iso = price_obj.get("currency_iso_code") or price_obj.get("currency")
        if iso:
            currency = str(iso).upper()
    elif isinstance(price_obj, (int, float)):
        price = float(price_obj)

    # Images
    image_url = ""
    images = ad.get("images") or ad.get("pictures") or []
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            # Try common nested keys
            image_url = (
                first.get("url")
                or first.get("uri")
                or first.get("link")
                or ""
            )
        elif isinstance(first, str):
            image_url = first
    elif isinstance(images, dict):
        urls = images.get("urls") or images.get("image") or []
        if isinstance(urls, list) and urls:
            image_url = urls[0] if isinstance(urls[0], str) else ""
        elif isinstance(urls, str):
            image_url = urls

    # URL — selfLink or constructed
    url = ""
    self_link = ad.get("selfLink") or ad.get("self-link") or ad.get("link") or ""
    if isinstance(self_link, dict):
        url = self_link.get("href") or ""
    elif isinstance(self_link, str):
        url = self_link
    if not url and ad_id:
        url = f"https://www.kleinanzeigen.de/s-anzeige/{ad_id}"

    # Ensure URL is absolute
    if url and not url.startswith("http"):
        url = f"https://www.kleinanzeigen.de{url}"

    # Per-listing attributes. Kleinanzeigen API exposes ad attributes as
    # a flat list under various keys depending on category.
    listing_attrs: Dict[str, Any] = {}
    attrs = ad.get("attributes") or ad.get("ad-attributes") or []
    if isinstance(attrs, list):
        for attr in attrs:
            if not isinstance(attr, dict):
                continue
            name = (attr.get("name") or attr.get("key") or "").lower()
            value = attr.get("value") or attr.get("localized-value")
            if not name or not value:
                continue
            if "zustand" in name or "condition" in name:
                listing_attrs["condition"] = value
            elif "marke" in name or "brand" in name:
                listing_attrs["brand"] = value
            elif "farbe" in name or "color" in name:
                listing_attrs["color"] = value
            elif "groesse" in name or "size" in name:
                listing_attrs["size"] = value
            else:
                listing_attrs.setdefault("attributes_raw", {})[name] = value

    return {
        "source": "kleinanzeigen",
        "raw_id": f"kleinanzeigen-{ad_id}",
        "title": title[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": listing_attrs.get("condition"),
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
        "attributes": listing_attrs,
    }


def _normalize_html_ad(title: str, price_str: str, url: str, image_url: str) -> Dict[str, Any]:
    """Normalize a scraped HTML listing to the standard MarketHit format."""
    # Parse price — e.g. "150 \u20ac VB", "12,50 \u20ac", "VB" (negotiable, no price)
    price = 0.0
    currency = "EUR"
    if price_str:
        cleaned = price_str.replace(".", "").replace(",", ".").strip()
        match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if match:
            try:
                price = float(match.group(1))
            except (ValueError, TypeError):
                pass

    # Extract ad ID from URL if possible
    ad_id = ""
    id_match = re.search(r"/(\d{6,})", url or "")
    if id_match:
        ad_id = id_match.group(1)

    if url and not url.startswith("http"):
        url = f"https://www.kleinanzeigen.de{url}"

    return {
        "source": "kleinanzeigen",
        "raw_id": f"kleinanzeigen-{ad_id}" if ad_id else f"kleinanzeigen-html-{hash(title) % 10**8}",
        "title": title[:500],
        "price": price,
        "currency": currency,
        "source_price": price,
        "source_currency": currency,
        "url": url,
        "condition": None,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


def _parse_html_listings(html: str, limit: int) -> List[Dict[str, Any]]:
    """Parse listings from Kleinanzeigen HTML search results page.

    Uses regex to avoid a BeautifulSoup dependency.
    """
    results: List[Dict[str, Any]] = []

    # Each listing is in an <article> or a div with data-adid
    # Pattern: find ad cards with their key data
    ad_blocks = re.findall(
        r'<article[^>]*class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    if not ad_blocks:
        # Alternative: list items with ad links
        ad_blocks = re.findall(
            r'<li[^>]*class="[^"]*ad-listitem[^"]*"[^>]*>(.*?)</li>',
            html,
            re.DOTALL | re.IGNORECASE,
        )

    for block in ad_blocks[:limit]:
        # Title + URL from the main link
        link_match = re.search(
            r'<a[^>]*href="(/s-anzeige/[^"]+)"[^>]*>.*?</a>',
            block,
            re.DOTALL,
        )
        if not link_match:
            # Broader link pattern
            link_match = re.search(r'<a[^>]*href="(/s-[^"]+)"[^>]*>', block)

        url = link_match.group(1) if link_match else ""

        # Title
        title_match = re.search(
            r'class="[^"]*ellipsis[^"]*"[^>]*>([^<]+)<',
            block,
        )
        if not title_match:
            title_match = re.search(r'<h2[^>]*>([^<]+)<', block)
        if not title_match:
            title_match = re.search(r'data-testid="[^"]*title[^"]*"[^>]*>([^<]+)<', block)

        title = title_match.group(1).strip() if title_match else ""
        if not title:
            continue

        # Price
        price_match = re.search(
            r'class="[^"]*aditem-main--middle--price[^"]*"[^>]*>([^<]+)<',
            block,
        )
        if not price_match:
            price_match = re.search(r'(\d[\d.,]*\s*\u20ac)', block)
        price_str = price_match.group(1).strip() if price_match else ""

        # Image
        img_match = re.search(r'<img[^>]*src="(https?://[^"]+)"', block)
        image_url = img_match.group(1) if img_match else ""

        results.append(_normalize_html_ad(title, price_str, url, image_url))

    return results


class KleinanzeigenCaller:
    """Async Kleinanzeigen adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os

        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("KLEINANZEIGEN_ENABLED", "true").lower() == "true"
        )
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Accept": "application/json",
                },
                follow_redirects=True,
            )
        return self._http

    async def _search_api(
        self,
        query: str,
        limit: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Try the JSON API. Returns None if the API is unavailable."""
        client = await self._client()
        params = {
            "q": query,
            "page": 0,
            "size": min(limit, 25),
        }
        resp = await client.get(KLEINANZEIGEN_API_URL, params=params)

        if resp.status_code == 200:
            data = resp.json()
            # API may nest ads under different keys
            ads = (
                data.get("ads")
                or data.get("{http://www.ebayclassifiedsgroup.com/schema/ad/v1}ads", {}).get("value", [])
                or data.get("value", [])
                or []
            )
            if isinstance(ads, dict):
                ads = ads.get("ad") or ads.get("ads") or []
            return [_normalize_api_ad(ad) for ad in ads[:limit]]

        if resp.status_code in (403, 406, 451):
            # API is blocked — caller should fall back to HTML
            logger.info("Kleinanzeigen API returned %d — falling back to HTML", resp.status_code)
            return None

        if resp.status_code in (429, 503):
            kleinanzeigen_circuit.record_failure()
            logger.warning("Kleinanzeigen API returned %d", resp.status_code)
            return []

        return None  # unknown status — try HTML fallback

    async def _search_html(
        self,
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape the public HTML search page."""
        client = await self._client()
        url = KLEINANZEIGEN_HTML_URL.format(query=quote_plus(query))
        resp = await client.get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
            },
        )

        if resp.status_code != 200:
            logger.warning("Kleinanzeigen HTML search returned %d", resp.status_code)
            return []

        return _parse_html_listings(resp.text, limit)

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Kleinanzeigen for active listings."""
        if not self.configured:
            return []

        try:
            kleinanzeigen_circuit.check()
        except CircuitOpenError:
            logger.warning("Kleinanzeigen circuit open -- skipping")
            return []

        try:
            # Try JSON API first
            results = await self._search_api(query, limit)

            # Fall back to HTML scraping if API is unavailable
            if results is None:
                results = await self._search_html(query, limit)

            kleinanzeigen_circuit.record_success()
            return results

        except Exception as exc:
            kleinanzeigen_circuit.record_failure()
            logger.warning("Kleinanzeigen search error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Kleinanzeigen does not expose sold/completed listings -- returns empty.

        The search() method returns active listings only.  For valuation
        purposes other adapters (eBay sold, Catawiki sold, Mavin) should
        be preferred.
        """
        return []

    async def health_check(self) -> bool:
        """Check if Kleinanzeigen is reachable."""
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                KLEINANZEIGEN_API_URL,
                params={"q": "test", "page": 0, "size": 1},
            )
            # API or HTML — either reachable is fine
            if resp.status_code in (200, 403):
                return True
            # Try HTML as fallback check
            resp = await client.get(
                KLEINANZEIGEN_HTML_URL.format(query="test"),
                headers={"Accept": "text/html"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
