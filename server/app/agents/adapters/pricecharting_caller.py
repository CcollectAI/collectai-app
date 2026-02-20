"""
PriceCharting API caller for the Marketplace Aggregation Agent.

PriceCharting is the industry standard for retro video game pricing.
Also covers consoles, handhelds, and some trading cards.

API docs: https://www.pricecharting.com/api-documentation

Env vars:
    PRICECHARTING_API_KEY - API key from PriceCharting account
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import PRICECHARTING_API_KEY as _CFG_KEY
from workers.circuit_breaker import pricecharting_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRICECHARTING_BASE = "https://www.pricecharting.com/api"

# Categories that benefit from PriceCharting data
SUPPORTED_CATEGORIES = [
    "retro_games",
    "retro_handhelds",
    "pokemon",  # Pokemon game cartridges
    "nintendo_merch",  # amiibo pricing
]

# Console name mapping for PriceCharting queries
PLATFORM_MAP: Dict[str, str] = {
    "NES": "nes",
    "SNES": "super-nintendo",
    "N64": "nintendo-64",
    "GameCube": "gamecube",
    "Game Boy": "gameboy",
    "GBA": "gameboy-advance",
    "DS": "nintendo-ds",
    "Genesis": "sega-genesis",
    "Saturn": "sega-saturn",
    "Dreamcast": "sega-dreamcast",
    "PS1": "playstation",
    "PS2": "playstation-2",
    "Xbox": "xbox",
    "Atari": "atari-2600",
    "Wii": "wii",
    "PSP": "psp",
    "PS Vita": "playstation-vita",
}

PRICECHARTING_SOURCE_RELIABILITY = 0.90


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a PriceCharting product into a standard MarketHit dict."""
    product_name = product.get("product-name", "Unknown")
    console = product.get("console-name", "")

    # PriceCharting prices are in USD cents
    loose = product.get("loose-price", 0) / 100.0 if product.get("loose-price") else 0
    cib = product.get("cib-price", 0) / 100.0 if product.get("cib-price") else 0
    new_price = product.get("new-price", 0) / 100.0 if product.get("new-price") else 0
    graded = product.get("graded-price", 0) / 100.0 if product.get("graded-price") else 0

    # Use CIB as primary price, fall back to loose
    primary_price = cib if cib > 0 else loose

    return {
        "source": "pricecharting",
        "raw_id": f"pricecharting-{product.get('id', '')}",
        "title": f"{product_name} ({console})" if console else product_name,
        "price": primary_price,
        "currency": "USD",
        "source_price": primary_price,
        "source_currency": "USD",
        "url": f"https://www.pricecharting.com/game/{product.get('id', '')}",
        "condition": None,
        "image_url": "",
        "is_sold": False,
        "price_loose": loose,
        "price_cib": cib,
        "price_new": new_price,
        "price_graded": graded,
        "console": console,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class PriceChartingCaller:
    """Async PriceCharting API caller for the marketplace aggregation agent."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or _CFG_KEY
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def search(
        self,
        query: str,
        category: str = "retro_games",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search PriceCharting for products matching a query."""
        if not self.configured:
            logger.debug("PriceCharting not configured — skipping search")
            return []

        try:
            pricecharting_circuit.check()
        except CircuitOpenError:
            logger.warning("PriceCharting circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                f"{PRICECHARTING_BASE}/products",
                params={
                    "t": self.api_key,
                    "q": query,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            pricecharting_circuit.record_success()

            products = data.get("products", [])
            if isinstance(products, dict):
                products = [products]

            return [_normalize_product(p) for p in products[:limit]]

        except Exception as exc:
            pricecharting_circuit.record_failure()
            logger.warning("PriceCharting search error: %s", exc)
            return []

    async def lookup(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Look up a specific product by PriceCharting ID."""
        if not self.configured:
            return None

        try:
            pricecharting_circuit.check()
        except CircuitOpenError:
            return None

        try:
            client = await self._client()
            resp = await client.get(
                f"{PRICECHARTING_BASE}/product",
                params={"t": self.api_key, "id": product_id},
            )
            resp.raise_for_status()
            data = resp.json()
            pricecharting_circuit.record_success()
            return _normalize_product(data)

        except Exception as exc:
            pricecharting_circuit.record_failure()
            logger.warning("PriceCharting lookup error: %s", exc)
            return None

    async def sold_comps(
        self,
        query: str,
        category: str = "retro_games",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """PriceCharting prices are aggregated from sold data — return as sold comps."""
        results = await self.search(query, category, limit)
        for r in results:
            r["is_sold"] = True
        return results

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                f"{PRICECHARTING_BASE}/products",
                params={"t": self.api_key, "q": "mario"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
