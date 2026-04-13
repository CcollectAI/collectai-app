"""
Depop marketplace adapter for the Marketplace Aggregation Agent.

Depop is a UK-based fashion and collectibles resale platform popular
with younger collectors for streetwear, sneakers, vintage, and K-pop merch.
Uses the public web API.

Primary region: UK, US
Prices in GBP/USD.

Env vars:
    DEPOP_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import depop_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

DEPOP_SOURCE_RELIABILITY = 0.65
DEPOP_SOLD_RELIABILITY = 0.70

DEPOP_API_URL = "https://webapi.depop.com/api/v2/search/products"
DEPOP_ENABLED = os.getenv("DEPOP_ENABLED", "true").lower() in ("true", "1", "yes")

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


class DepopCaller:
    """Depop UK/US search adapter."""

    source_name = "depop"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json",
                },
            )
        return self._client

    def configured(self) -> bool:
        return DEPOP_ENABLED

    async def search(
        self,
        query: str,
        limit: int = 20,
        region: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search Depop for active listings."""
        if not self.configured():
            return []

        try:
            depop_circuit.check()
        except CircuitOpenError:
            logger.warning("Depop circuit open — skipping")
            return []

        client = await self._get_client()
        params = {
            "what": query,
            "itemsPerPage": str(min(limit, 24)),
            "country": "gb" if region in ("europe", "uk", "gb") else "us",
        }

        try:
            resp = await client.get(DEPOP_API_URL, params=params)
            if resp.status_code == 429:
                depop_circuit.record_failure()
                logger.warning("[Depop] Rate limited (429)")
                return []
            resp.raise_for_status()
            depop_circuit.record_success()
        except Exception as e:
            depop_circuit.record_failure()
            logger.error("[Depop] Search failed: %s", e)
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        products = data.get("products", [])
        results: List[Dict[str, Any]] = []

        for item in products[:limit]:
            try:
                price_obj = item.get("price", {})
                if isinstance(price_obj, dict):
                    price = float(price_obj.get("priceAmount", 0))
                    currency = price_obj.get("currencyName", "GBP")
                elif isinstance(price_obj, (int, float)):
                    price = float(price_obj)
                    currency = "GBP"
                else:
                    continue

                if price <= 0:
                    continue

                slug = item.get("slug", "")
                item_id = str(item.get("id", ""))
                seller = item.get("seller", {})
                seller_name = seller.get("username", "") if isinstance(seller, dict) else ""

                image_url = ""
                previews = item.get("preview", {})
                if isinstance(previews, dict):
                    image_url = previews.get("640", "") or previews.get("320", "")
                elif isinstance(previews, list) and previews:
                    image_url = previews[0] if isinstance(previews[0], str) else ""

                results.append({
                    "source": "depop",
                    "raw_id": f"depop-{item_id}",
                    "title": item.get("description", slug)[:200],
                    "price": price,
                    "currency": currency,
                    "url": f"https://www.depop.com/products/{slug}/" if slug else "",
                    "image_url": image_url,
                    "condition": None,
                    "is_sold": bool(item.get("status") == "sold"),
                    "seller_name": seller_name,
                })
            except Exception as e:
                logger.debug("[Depop] Failed to parse item: %s", e)
                continue

        return results

    async def sold_comps(
        self,
        query: str,
        limit: int = 20,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search for sold items on Depop."""
        # Depop shows sold items in regular search with status=sold
        results = await self.search(query, limit=limit, **kwargs)
        return [r for r in results if r.get("is_sold")]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "source": "depop",
            "configured": self.configured(),
            "circuit_closed": not depop_circuit.is_open(),
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
