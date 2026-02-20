"""
StockX API caller for the Marketplace Aggregation Agent.

StockX is a major marketplace for sneakers, streetwear, and designer
collectibles. Covers designer_toys, funko, kpop_merch, and taylor_swift.

Env vars:
    STOCKX_API_KEY - StockX API key
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import STOCKX_API_KEY as _CFG_KEY
from workers.circuit_breaker import stockx_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STOCKX_BASE = "https://api.stockx.com/v2"
STOCKX_BROWSE = "https://api.stockx.com/v2/catalog/search"

# Categories that benefit from StockX data
SUPPORTED_CATEGORIES = [
    "designer_toys",
    "funko",
    "kpop_merch",
    "taylor_swift",
    "pop_fandom",
    "loungefly",
    "hot_toys",
]

STOCKX_SOURCE_RELIABILITY = 0.85


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a StockX product search result."""
    attrs = product.get("attributes", {})
    market = product.get("market", {}) or product.get("salesInformation", {})

    title = product.get("title") or product.get("name") or "Unknown"
    image = product.get("media", {}).get("thumbUrl") or product.get("media", {}).get("imageUrl") or ""
    product_id = product.get("id") or product.get("urlKey") or ""

    # StockX uses last_sale, lowest_ask, highest_bid
    last_sale = market.get("lastSale") or market.get("lastSalePrice") or 0
    lowest_ask = market.get("lowestAsk") or market.get("lowestAskPrice") or 0
    highest_bid = market.get("highestBid") or market.get("highestBidPrice") or 0

    # Use last sale as primary, fall back to lowest ask
    price = float(last_sale) if last_sale else float(lowest_ask) if lowest_ask else 0

    return {
        "source": "stockx",
        "raw_id": f"stockx-{product_id}",
        "title": title,
        "price": price,
        "currency": "USD",
        "source_price": price,
        "source_currency": "USD",
        "url": f"https://stockx.com/{product.get('urlKey', product_id)}",
        "condition": "New",  # StockX only sells deadstock/new
        "image_url": image,
        "is_sold": False,
        "last_sale": float(last_sale) if last_sale else None,
        "lowest_ask": float(lowest_ask) if lowest_ask else None,
        "highest_bid": float(highest_bid) if highest_bid else None,
        "retail_price": float(attrs.get("retailPrice", 0)) if attrs.get("retailPrice") else None,
        "release_date": attrs.get("releaseDate"),
        "brand": attrs.get("brand") or product.get("brand"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class StockXCaller:
    """Async StockX API caller for the marketplace aggregation agent."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or _CFG_KEY
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "x-api-key": self.api_key,
                    "Accept": "application/json",
                },
            )
        return self._http

    async def search(
        self,
        query: str,
        category: str = "designer_toys",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search StockX catalog for products matching a query."""
        if not self.configured:
            logger.debug("StockX not configured — skipping search")
            return []

        try:
            stockx_circuit.check()
        except CircuitOpenError:
            logger.warning("StockX circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                STOCKX_BROWSE,
                params={
                    "query": query,
                    "pageSize": str(min(limit, 40)),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            stockx_circuit.record_success()

            products = data.get("products", data.get("results", []))
            return [_normalize_product(p) for p in products[:limit]]

        except Exception as exc:
            stockx_circuit.record_failure()
            logger.warning("StockX search error: %s", exc)
            return []

    async def lookup(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Look up a specific StockX product by ID or URL key."""
        if not self.configured:
            return None

        try:
            stockx_circuit.check()
        except CircuitOpenError:
            return None

        try:
            client = await self._client()
            resp = await client.get(f"{STOCKX_BASE}/catalog/products/{product_id}")
            resp.raise_for_status()
            data = resp.json()
            stockx_circuit.record_success()
            return _normalize_product(data.get("product", data))

        except Exception as exc:
            stockx_circuit.record_failure()
            logger.warning("StockX lookup error: %s", exc)
            return None

    async def sold_comps(
        self,
        query: str,
        category: str = "designer_toys",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """StockX last_sale represents actual sold data — return as sold comps."""
        results = await self.search(query, category, limit)
        for r in results:
            if r.get("last_sale"):
                r["is_sold"] = True
                r["price"] = r["last_sale"]
                r["source_price"] = r["last_sale"]
        return [r for r in results if r.get("is_sold")]

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(STOCKX_BROWSE, params={"query": "test", "pageSize": "1"})
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
