"""
Catawiki marketplace adapter for the Marketplace Aggregation Agent.

Catawiki is a European online auction house specializing in luxury and niche
collectibles.  Uses the Catawiki buyer JSON API when available, with a fallback
to HTML scraping of the search page.

Prices are in EUR (European marketplace).

Covers: watches, comic_books, vintage_toys, designer_toys, pens, whiskey,
fragrances, anime_figures, sportscards, vinyl_records, diecast, art, coins.

Env vars:
    CATAWIKI_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import catawiki_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

CATAWIKI_SOURCE_RELIABILITY = 0.80
CATAWIKI_SOLD_RELIABILITY = 0.90

# Catawiki buyer API (publicly accessible JSON)
CATAWIKI_API_URL = "https://www.catawiki.com/buyer/api/v1/search"

# Fallback: scrape the search page
CATAWIKI_SEARCH_PAGE = "https://www.catawiki.com/en/s?q={query}"


def _normalize_lot(lot: Dict[str, Any], is_sold: bool = False) -> Dict[str, Any]:
    """Normalize a Catawiki lot to the standard MarketHit format."""
    lot_id = lot.get("id") or lot.get("lot_id") or ""
    title = lot.get("title") or lot.get("name") or "Unknown"

    # Price extraction — try multiple fields
    price = 0.0
    for price_field in ("current_bid", "hammer_price", "price", "estimate_min", "bid_amount"):
        val = lot.get(price_field)
        if val:
            try:
                price = float(val)
                if price > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Estimate range (Catawiki provides expert estimates)
    estimate_min = lot.get("estimate_min") or lot.get("low_estimate")
    estimate_max = lot.get("estimate_max") or lot.get("high_estimate")

    # Image URL
    image_url = ""
    images = lot.get("images") or lot.get("photos") or []
    if images and isinstance(images, list):
        first = images[0]
        if isinstance(first, str):
            image_url = first
        elif isinstance(first, dict):
            image_url = first.get("url") or first.get("large") or first.get("medium") or ""
    elif lot.get("image_url"):
        image_url = lot["image_url"]
    elif lot.get("thumbnail_url"):
        image_url = lot["thumbnail_url"]

    # Condition
    condition = lot.get("condition") or lot.get("condition_description")

    # Sold date
    sold_at = lot.get("closed_at") or lot.get("end_date") or lot.get("sold_at") if is_sold else None

    # URL
    slug = lot.get("slug") or lot.get("url_slug") or ""
    if slug:
        url = f"https://www.catawiki.com/en/l/{lot_id}-{slug}"
    else:
        url = f"https://www.catawiki.com/en/l/{lot_id}" if lot_id else CATAWIKI_SEARCH_PAGE.format(query="")

    return {
        "source": "catawiki",
        "raw_id": f"catawiki-{lot_id}",
        "title": title[:500],
        "price": price,
        "currency": "EUR",
        "source_price": price,
        "source_currency": "EUR",
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": sold_at,
        "estimate_min": float(estimate_min) if estimate_min else None,
        "estimate_max": float(estimate_max) if estimate_max else None,
    }


class CatawikiCaller:
    """Async Catawiki adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("CATAWIKI_ENABLED", "true").lower() == "true"
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
                    "Accept": "application/json",
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
        """Search Catawiki for active auction listings."""
        if not self.configured:
            return []

        try:
            catawiki_circuit.check()
        except CircuitOpenError:
            logger.warning("Catawiki circuit open -- skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                CATAWIKI_API_URL,
                params={
                    "q": query,
                    "page": "1",
                    "per_page": str(min(limit, 20)),
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                lots = data.get("lots") or data.get("results") or data.get("data") or data.get("items", [])
                catawiki_circuit.record_success()
                return [_normalize_lot(lot, is_sold=False) for lot in lots[:limit]]

            if resp.status_code in (429, 503):
                catawiki_circuit.record_failure()
                logger.warning("Catawiki API returned %d", resp.status_code)
                return []

            # Fallback to HTML scraping
            logger.debug("Catawiki API returned %d, attempting page scrape", resp.status_code)
            return await self._scrape_search(query, limit)

        except Exception as exc:
            catawiki_circuit.record_failure()
            logger.warning("Catawiki search error: %s", exc)
            return []

    async def _scrape_search(
        self, query: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape Catawiki search page for listings."""
        try:
            client = await self._client()
            url = CATAWIKI_SEARCH_PAGE.format(query=quote_plus(query))
            resp = await client.get(url)
            if resp.status_code != 200:
                catawiki_circuit.record_failure()
                return []

            catawiki_circuit.record_success()

            text = resp.text
            results = []

            # Look for lot patterns in the HTML
            lot_pattern = re.compile(r'/en/l/(\d+)-([^"\']+)')
            price_pattern = re.compile(r'[\u20ac](\d+(?:[.,]\d{3})*(?:[.,]\d{2})?)')

            lots_found = list(set(lot_pattern.findall(text)))[:limit]
            prices_found = price_pattern.findall(text)

            for i, (lot_id, slug) in enumerate(lots_found):
                price = 0.0
                if i < len(prices_found):
                    try:
                        price = float(prices_found[i].replace(",", "").replace(".", "").rstrip("0") or "0")
                        # Re-parse for proper decimal handling
                        raw = prices_found[i]
                        if "," in raw and "." in raw:
                            price = float(raw.replace(".", "").replace(",", "."))
                        elif "," in raw:
                            price = float(raw.replace(",", "."))
                        else:
                            price = float(raw)
                    except (ValueError, TypeError):
                        price = 0.0

                results.append({
                    "source": "catawiki",
                    "raw_id": f"catawiki-{lot_id}",
                    "title": slug.replace("-", " ").title()[:500],
                    "price": price,
                    "currency": "EUR",
                    "source_price": price,
                    "source_currency": "EUR",
                    "url": f"https://www.catawiki.com/en/l/{lot_id}-{slug}",
                    "condition": None,
                    "image_url": "",
                    "is_sold": False,
                })

            return results[:limit]

        except Exception as exc:
            catawiki_circuit.record_failure()
            logger.warning("Catawiki scrape error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Catawiki for closed/sold auction lots (hammer prices)."""
        if not self.configured:
            return []

        try:
            catawiki_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                CATAWIKI_API_URL,
                params={
                    "q": query,
                    "status": "closed",
                    "page": "1",
                    "per_page": str(min(limit, 20)),
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                lots = data.get("lots") or data.get("results") or data.get("data") or data.get("items", [])
                catawiki_circuit.record_success()
                return [_normalize_lot(lot, is_sold=True) for lot in lots[:limit]]

            if resp.status_code in (429, 503):
                catawiki_circuit.record_failure()
                return []

            catawiki_circuit.record_success()
            return []

        except Exception as exc:
            catawiki_circuit.record_failure()
            logger.warning("Catawiki sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                CATAWIKI_API_URL,
                params={"q": "test", "per_page": "1"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
