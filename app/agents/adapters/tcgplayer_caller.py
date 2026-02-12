"""
TCGPlayer API caller for the Marketplace Aggregation Agent.

Calls the TCGPlayer API v1.39.0 for searching TCG product catalogs
and retrieving market price data.

Env vars:
    TCGPLAYER_BEARER_TOKEN - Bearer token for TCGPlayer API
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import TCGPLAYER_BEARER_TOKEN as _CFG_TCGPLAYER_BEARER_TOKEN
from workers.circuit_breaker import tcgplayer_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TCGPLAYER_BASE = "https://api.tcgplayer.com/v1.39.0"

# TCGPlayer category IDs for CollectAI's TCG categories
CATEGORY_TO_TCGPLAYER_ID: Dict[str, int] = {
    "pokemon": 3,
    "mtg": 1,
    "yugioh": 2,
    "lorcana": 71,
}

SUPPORTED_CATEGORIES = list(CATEGORY_TO_TCGPLAYER_ID.keys())


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _convert_usd_to_eur(usd: float, rates: dict[str, float] | None = None) -> float:
    rate = (rates or {}).get("USD")
    if rate is None:
        from app.config import USD_TO_EUR
        rate = USD_TO_EUR
    return round(usd * rate, 2)


def _normalize_catalog_product(
    product: Dict[str, Any],
    price_map: Optional[Dict[int, Dict[str, Any]]] = None,
    rates: dict[str, float] | None = None,
) -> Dict[str, Any]:
    """Normalize a TCGPlayer catalog product to a MarketHit dict."""
    product_id = product.get("productId") or product.get("productID", "")
    raw_id = str(product_id)

    price_data = (price_map or {}).get(int(product_id)) if product_id else None
    raw_price = 0.0
    if price_data:
        raw_price = price_data.get("marketPrice") or price_data.get("midPrice") or 0.0
    elif product.get("marketPrice"):
        raw_price = product["marketPrice"]

    product_url = product.get("url")
    if product_url:
        url = f"https://www.tcgplayer.com{product_url}"
    else:
        url = f"https://www.tcgplayer.com/product/{raw_id}"

    return {
        "source": "tcgplayer",
        "raw_id": raw_id,
        "title": product.get("name") or product.get("productName", ""),
        "price": _convert_usd_to_eur(raw_price, rates),
        "currency": "EUR",
        "source_price": raw_price,
        "source_currency": "USD",
        "sold_at": None,
        "url": url,
        "condition": None,
        "image_url": product.get("imageUrl") or product.get("image"),
        "is_sold": False,
    }


def _normalize_price_entry(
    entry: Dict[str, Any],
    product_name: Optional[str] = None,
    rates: dict[str, float] | None = None,
) -> Dict[str, Any]:
    """Normalize a TCGPlayer pricing entry as a sold-comp MarketHit dict."""
    product_id = entry.get("productId", "")
    raw_id = str(product_id)
    raw_price = entry.get("marketPrice") or entry.get("midPrice") or 0.0
    condition = entry.get("subTypeName") or entry.get("condition")

    return {
        "source": "tcgplayer",
        "raw_id": raw_id,
        "title": product_name or f"TCGPlayer #{raw_id}",
        "price": _convert_usd_to_eur(raw_price, rates),
        "currency": "EUR",
        "source_price": raw_price,
        "source_currency": "USD",
        "sold_at": entry.get("lastUpdated"),
        "url": f"https://www.tcgplayer.com/product/{raw_id}",
        "condition": condition,
        "image_url": None,
        "is_sold": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TCGPlayerCaller:
    """Async TCGPlayer API caller for the marketplace aggregation agent."""

    def __init__(self, bearer_token: Optional[str] = None):
        self.bearer_token = bearer_token or _CFG_TCGPLAYER_BEARER_TOKEN
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.bearer_token)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _resolve_category_id(self, category: Optional[str]) -> Optional[int]:
        if not category:
            return None
        return CATEGORY_TO_TCGPLAYER_ID.get(category)

    async def _fetch_prices(
        self,
        client: httpx.AsyncClient,
        product_ids: List[int],
    ) -> Dict[int, Dict[str, Any]]:
        """Fetch market prices for a list of product IDs."""
        price_map: Dict[int, Dict[str, Any]] = {}
        if not product_ids:
            return price_map

        try:
            id_str = ",".join(str(pid) for pid in product_ids)
            url = f"{TCGPLAYER_BASE}/pricing/product/{id_str}"
            resp = await client.get(url, headers=self._headers())
            if not resp.is_success:
                logger.warning("[TCGPlayerCaller] fetchPrices failed (%d)", resp.status_code)
                return price_map

            data = resp.json()
            for entry in data.get("results", []):
                pid = entry.get("productId")
                if pid is not None:
                    # Prefer "Normal" sub-type; keep first seen otherwise
                    if pid not in price_map or entry.get("subTypeName") == "Normal":
                        price_map[pid] = entry

        except Exception:
            logger.warning("[TCGPlayerCaller] fetchPrices error", exc_info=True)

        return price_map

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search TCGPlayer catalog for products.

        Returns a list of normalized MarketHit dicts.
        """
        if not self.configured:
            logger.warning("[TCGPlayerCaller] Not configured (missing TCGPLAYER_BEARER_TOKEN)")
            return []

        try:
            tcgplayer_circuit.check()
        except CircuitOpenError:
            logger.warning("[TCGPlayerCaller] Circuit breaker OPEN — skipping search")
            return []

        # Fetch live FX rates once for this call
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        client = await self._get_client()
        tcg_category_id = self._resolve_category_id(category)

        params: Dict[str, str] = {
            "productName": query,
            "limit": str(min(limit, 100)),
            "offset": "0",
        }
        if tcg_category_id is not None:
            params["categoryId"] = str(tcg_category_id)

        catalog_url = f"{TCGPLAYER_BASE}/catalog/products"

        try:
            resp = await client.get(catalog_url, params=params, headers=self._headers())

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "unknown")
                logger.warning("[TCGPlayerCaller] Rate limited (Retry-After: %s)", retry_after)
                return []

            resp.raise_for_status()
            data = resp.json()
            products = data.get("results", [])

            # Fetch prices for returned products
            product_ids = []
            for p in products:
                pid = p.get("productId") or p.get("productID")
                if pid is not None:
                    product_ids.append(int(pid))

            price_map = await self._fetch_prices(client, product_ids)
            tcgplayer_circuit.record_success()
            return [_normalize_catalog_product(p, price_map, rates) for p in products]

        except httpx.HTTPStatusError as e:
            tcgplayer_circuit.record_failure()
            logger.error("[TCGPlayerCaller] Catalog API HTTP error: %d", e.response.status_code)
            return []
        except httpx.RequestError:
            tcgplayer_circuit.record_failure()
            logger.error("[TCGPlayerCaller] Catalog API request failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get sold comparables by searching products then fetching their pricing.

        TCGPlayer's pricing endpoint returns market prices which serve as
        sold-comp equivalents.

        Returns a list of normalized MarketHit dicts with is_sold=True.
        """
        if not self.configured:
            logger.warning("[TCGPlayerCaller] Not configured (missing TCGPLAYER_BEARER_TOKEN)")
            return []

        # Step 1: search for products to get IDs
        search_results = await self.search(query, category=category, limit=min(limit, 10))
        if not search_results:
            return []

        # Fetch live FX rates once for this call
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        client = await self._get_client()

        # Step 2: fetch detailed pricing for those products
        product_ids = []
        name_map: Dict[str, str] = {}
        for hit in search_results:
            raw_id = hit.get("raw_id", "")
            try:
                product_ids.append(int(raw_id))
            except (ValueError, TypeError):
                continue
            name_map[raw_id] = hit.get("title", "")

        if not product_ids:
            return []

        try:
            id_str = ",".join(str(pid) for pid in product_ids)
            price_url = f"{TCGPLAYER_BASE}/pricing/product/{id_str}"
            resp = await client.get(price_url, headers=self._headers())

            if resp.status_code == 429:
                logger.warning("[TCGPlayerCaller] soldComps rate limited")
                return []

            resp.raise_for_status()
            data = resp.json()
            price_entries = data.get("results", [])

            hits = []
            for entry in price_entries:
                market_price = entry.get("marketPrice")
                if market_price is not None and market_price > 0:
                    pid = str(entry.get("productId", ""))
                    name = name_map.get(pid)
                    hits.append(_normalize_price_entry(entry, name, rates))

            tcgplayer_circuit.record_success()
            return hits

        except httpx.HTTPStatusError as e:
            tcgplayer_circuit.record_failure()
            logger.error("[TCGPlayerCaller] Pricing API HTTP error: %d", e.response.status_code)
            return []
        except httpx.RequestError:
            tcgplayer_circuit.record_failure()
            logger.error("[TCGPlayerCaller] Pricing API request failed", exc_info=True)
            return []

    async def health_check(self) -> bool:
        """Check if TCGPlayer API is reachable and token is valid."""
        if not self.configured:
            return False
        try:
            results = await self.search("pikachu", category="pokemon", limit=1)
            return True
        except Exception:
            return False
