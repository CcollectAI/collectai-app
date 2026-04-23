"""
Whisky Auctioneer marketplace adapter for the Marketplace Aggregation Agent.

Whisky Auctioneer is the world's largest online whisky auction.  Uses httpx
to scrape search results and past auction results for hammer prices.

Native prices are in GBP; converted to EUR via pipelines.import_common.to_eur.

Covers: whiskey only.

Env vars:
    WHISKY_AUCTIONEER_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import whisky_auctioneer_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

WHISKY_AUCTIONEER_SOURCE_RELIABILITY = 0.85
WHISKY_AUCTIONEER_SOLD_RELIABILITY = 0.95

# Search endpoints
WHISKY_AUCTIONEER_SEARCH_URL = "https://www.whiskyauctioneer.com/search"
WHISKY_AUCTIONEER_RESULTS_URL = "https://www.whiskyauctioneer.com/auction-results"


def _gbp_to_eur(price_gbp: float) -> float:
    """Convert GBP price to EUR using live rates with fallback."""
    try:
        from pipelines.import_common import to_eur
        return to_eur(price_gbp, "GBP")
    except Exception:
        # Fallback rate if import_common is unavailable
        return price_gbp * 1.16


def _parse_gbp_price(text: str) -> float:
    """Extract a GBP price from text like '\u00a3120', '\u00a31,250.00', 'GBP 450'."""
    if not text:
        return 0.0

    # Match \u00a3 symbol or GBP prefix
    patterns = [
        r'\xc2?\xa3([\d,]+(?:\.\d{2})?)',       # \u00a3 symbol (raw bytes)
        r'\u00a3([\d,]+(?:\.\d{2})?)',           # \u00a3 symbol (unicode)
        r'GBP\s*([\d,]+(?:\.\d{2})?)',           # GBP prefix
        r'gbp\s*([\d,]+(?:\.\d{2})?)',           # gbp lowercase
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (ValueError, TypeError):
                continue

    return 0.0


def _normalize_lot(
    lot: Dict[str, Any],
    is_sold: bool = False,
) -> Dict[str, Any]:
    """Normalize a Whisky Auctioneer lot to the standard MarketHit format."""
    lot_id = lot.get("id") or lot.get("lot_id") or lot.get("nid") or ""
    title = lot.get("title") or lot.get("name") or "Unknown"

    # Price in GBP
    price_gbp = 0.0
    for price_field in ("hammer_price", "current_bid", "price", "winning_bid"):
        val = lot.get(price_field)
        if val:
            try:
                price_gbp = float(val)
                if price_gbp > 0:
                    break
            except (ValueError, TypeError):
                continue

    # Convert to EUR
    price_eur = _gbp_to_eur(price_gbp) if price_gbp > 0 else 0.0

    # Image URL
    image_url = lot.get("image_url") or lot.get("image") or lot.get("thumbnail") or ""

    # Lot URL
    url = lot.get("url") or lot.get("path") or ""
    if url and not url.startswith("http"):
        url = f"https://www.whiskyauctioneer.com{url}"
    elif not url and lot_id:
        url = f"https://www.whiskyauctioneer.com/lot/{lot_id}"

    # Sold date
    sold_at = lot.get("end_date") or lot.get("sold_at") or lot.get("closed_at") if is_sold else None

    # Condition / details
    condition = lot.get("condition") or lot.get("bottle_size")

    return {
        "source": "whisky_auctioneer",
        "raw_id": f"whisky-auc-{lot_id}",
        "title": title[:500],
        "price": price_eur,
        "currency": "EUR",
        "source_price": price_gbp,
        "source_currency": "GBP",
        "url": url,
        "condition": condition,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": sold_at,
    }


class WhiskyAuctioneerCaller:
    """Async Whisky Auctioneer adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("WHISKY_AUCTIONEER_ENABLED", "true").lower() == "true"
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
        """Search Whisky Auctioneer for current auction lots."""
        if not self.configured:
            return []

        try:
            whisky_auctioneer_circuit.check()
        except CircuitOpenError:
            logger.warning("Whisky Auctioneer circuit open -- skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                WHISKY_AUCTIONEER_SEARCH_URL,
                params={"q": query},
            )

            # 2026-04-23 silent-failure sweep: any auth/rate/server error trips
            # the circuit. Was special-casing 429/503 + recording SUCCESS on
            # all other non-200 (incl. 401/403/451/5xx).
            if resp.status_code != 200:
                if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                    whisky_auctioneer_circuit.record_failure()
                    logger.warning("Whisky Auctioneer HTTP %d — circuit failure", resp.status_code)
                return []

            whisky_auctioneer_circuit.record_success()
            return self._parse_search_page(resp.text, query, limit, is_sold=False)

        except Exception as exc:
            whisky_auctioneer_circuit.record_failure()
            logger.warning("Whisky Auctioneer search error: %s", exc)
            return []

    def _parse_search_page(
        self,
        html: str,
        query: str,
        limit: int,
        is_sold: bool = False,
    ) -> List[Dict[str, Any]]:
        """Parse Whisky Auctioneer search/results page HTML."""
        results: List[Dict[str, Any]] = []

        # Try structured lot blocks first
        # Pattern: lot links with lot ID, title, price
        lot_blocks = re.findall(
            r'href="(/lot/[^"]*?(\d+)[^"]*)"[^>]*>.*?'
            r'class="[^"]*lot-title[^"]*"[^>]*>([^<]+)<.*?'
            r'(?:\xa3|GBP|&pound;)\s*([\d,]+(?:\.\d{2})?)',
            html,
            re.DOTALL | re.IGNORECASE,
        )

        for path, lot_id, title, price_str in lot_blocks[:limit]:
            try:
                price_gbp = float(price_str.replace(",", ""))
            except (ValueError, TypeError):
                price_gbp = 0.0

            price_eur = _gbp_to_eur(price_gbp) if price_gbp > 0 else 0.0

            results.append({
                "source": "whisky_auctioneer",
                "raw_id": f"whisky-auc-{lot_id}",
                "title": title.strip()[:500],
                "price": price_eur,
                "currency": "EUR",
                "source_price": price_gbp,
                "source_currency": "GBP",
                "url": f"https://www.whiskyauctioneer.com{path}" if path.startswith("/") else path,
                "condition": None,
                "image_url": "",
                "is_sold": is_sold,
            })

        # Fallback: simpler price extraction
        if not results:
            # Look for lot IDs and prices separately
            lot_ids = re.findall(r'/lot/[^"]*?(\d+)', html)
            prices = re.findall(r'(?:\xa3|&pound;|GBP)\s*([\d,]+(?:\.\d{2})?)', html, re.IGNORECASE)

            seen_ids = set()
            for i, lot_id in enumerate(lot_ids[:limit]):
                if lot_id in seen_ids:
                    continue
                seen_ids.add(lot_id)

                price_gbp = 0.0
                if i < len(prices):
                    try:
                        price_gbp = float(prices[i].replace(",", ""))
                    except (ValueError, TypeError):
                        price_gbp = 0.0

                price_eur = _gbp_to_eur(price_gbp) if price_gbp > 0 else 0.0

                results.append({
                    "source": "whisky_auctioneer",
                    "raw_id": f"whisky-auc-{lot_id}",
                    "title": query,
                    "price": price_eur,
                    "currency": "EUR",
                    "source_price": price_gbp,
                    "source_currency": "GBP",
                    "url": f"https://www.whiskyauctioneer.com/lot/{lot_id}",
                    "condition": None,
                    "image_url": "",
                    "is_sold": is_sold,
                })

        return results[:limit]

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Whisky Auctioneer past auction results for hammer prices."""
        if not self.configured:
            return []

        try:
            whisky_auctioneer_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                WHISKY_AUCTIONEER_RESULTS_URL,
                params={"q": query},
            )

            # Same fix as aggregate_search above (2026-04-23).
            if resp.status_code != 200:
                if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                    whisky_auctioneer_circuit.record_failure()
                    logger.warning("Whisky Auctioneer sold_comps HTTP %d — circuit failure", resp.status_code)
                return []

            whisky_auctioneer_circuit.record_success()
            return self._parse_search_page(resp.text, query, limit, is_sold=True)

        except Exception as exc:
            whisky_auctioneer_circuit.record_failure()
            logger.warning("Whisky Auctioneer sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                WHISKY_AUCTIONEER_SEARCH_URL,
                params={"q": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
