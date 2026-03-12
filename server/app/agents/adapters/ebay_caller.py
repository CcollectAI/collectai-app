"""
eBay API caller for the Marketplace Aggregation Agent.

Calls the eBay Browse API (v1) for active listings and the Finding API
for sold comparables. Uses OAuth 2.0 client credentials flow.

Env vars:
    EBAY_CLIENT_ID      - eBay application client ID
    EBAY_CLIENT_SECRET  - eBay application client secret
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import USD_TO_EUR, GBP_TO_EUR, JPY_TO_EUR

from app.config import EBAY_CLIENT_ID as _CFG_EBAY_CLIENT_ID, EBAY_CLIENT_SECRET as _CFG_EBAY_CLIENT_SECRET
from workers.circuit_breaker import ebay_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_BASE = "https://api.ebay.com/buy/browse/v1"
EBAY_FINDING_BASE = "https://svcs.ebay.com/services/search/FindingService/v1"


# ---------------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------------

_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}


async def _get_access_token(client: httpx.AsyncClient, client_id: str, client_secret: str) -> str:
    """Obtain or reuse a cached OAuth 2.0 application token."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = await client.post(
        EBAY_OAUTH_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        },
        content="grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope",
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 7200))
    return _token_cache["token"]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _convert_price(price: float, currency: str, rates: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Convert to EUR for legacy compat, but also preserve source currency/amount.

    *rates* is a foreign→EUR dict (e.g. {"USD": 0.92, "GBP": 1.16}).
    If not supplied, falls back to config defaults.
    """
    upper = currency.upper()
    result: Dict[str, Any] = {
        "source_price": price,
        "source_currency": upper,
    }
    if upper == "EUR":
        result.update(price=price, currency="EUR")
    else:
        rate = (rates or {}).get(upper)
        if rate is None:
            # Fallback to config
            _fallback = {"USD": USD_TO_EUR, "GBP": GBP_TO_EUR, "JPY": JPY_TO_EUR}
            rate = _fallback.get(upper)
        if rate is not None:
            result.update(price=round(price * rate, 2), currency="EUR")
        else:
            result.update(price=price, currency=upper)
    return result


def _normalize_browse_item(item: Dict[str, Any], rates: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Normalize an eBay Browse API item summary to a MarketHit dict."""
    raw_price = float(item.get("price", {}).get("value", 0) or 0)
    raw_currency = item.get("price", {}).get("currency", "USD")
    converted = _convert_price(raw_price, raw_currency, rates)
    raw_id = item.get("itemId", "")

    # Extract shipping data
    shipping_cost = None
    domestic_only = False
    ships_from = None

    shipping_opts = item.get("shippingOptions") or []
    if shipping_opts:
        first = shipping_opts[0]
        cost_type = (first.get("shippingCostType") or "").upper()
        if cost_type == "FREE":
            shipping_cost = 0.0
        elif cost_type == "FIXED":
            sc = first.get("shippingCost") or {}
            sc_val = float(sc.get("value", 0) or 0)
            sc_cur = sc.get("currency", "USD")
            if sc_val > 0:
                # Convert shipping to EUR
                sc_converted = _convert_price(sc_val, sc_cur, rates)
                shipping_cost = sc_converted["price"]

    ship_to = item.get("shipToLocations") or {}
    regions_included = ship_to.get("regionIncluded") or []
    if regions_included:
        region_ids = [r.get("regionId", "") for r in regions_included if isinstance(r, dict)]
        if region_ids == ["DOMESTIC"]:
            domestic_only = True

    item_location = item.get("itemLocation") or {}
    ships_from = item_location.get("country")

    return {
        "source": "ebay",
        "raw_id": str(raw_id),
        "title": item.get("title", ""),
        "price": converted["price"],
        "currency": converted["currency"],
        "source_price": converted.get("source_price"),
        "source_currency": converted.get("source_currency"),
        "sold_at": None,
        "url": item.get("itemWebUrl") or item.get("itemHref"),
        "condition": item.get("condition") or item.get("conditionId"),
        "image_url": (item.get("image") or {}).get("imageUrl"),
        "is_sold": False,
        "shipping_cost": shipping_cost,
        "domestic_only": domestic_only,
        "ships_from": ships_from,
    }


def _normalize_finding_item(item: Dict[str, Any], rates: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Normalize an eBay Finding API completed item to a MarketHit dict."""
    raw_price = 0.0
    try:
        raw_price = float(
            item.get("sellingStatus", [{}])[0]
            .get("currentPrice", [{}])[0]
            .get("__value__", 0)
        )
    except (IndexError, KeyError, TypeError, ValueError):
        pass

    raw_currency = "USD"
    try:
        raw_currency = (
            item.get("sellingStatus", [{}])[0]
            .get("currentPrice", [{}])[0]
            .get("@currencyId", "USD")
        )
    except (IndexError, KeyError, TypeError):
        pass

    converted = _convert_price(raw_price, raw_currency, rates)
    raw_id = ""
    try:
        raw_id = item.get("itemId", [""])[0]
    except (IndexError, TypeError):
        pass

    end_time = None
    try:
        end_time = item.get("listingInfo", [{}])[0].get("endTime", [None])[0]
    except (IndexError, KeyError, TypeError):
        pass

    condition_str = None
    try:
        condition_str = (
            item.get("condition", [{}])[0]
            .get("conditionDisplayName", [None])[0]
        )
    except (IndexError, KeyError, TypeError):
        pass

    image_url = None
    try:
        image_url = item.get("galleryURL", [None])[0]
    except (IndexError, TypeError):
        pass

    return {
        "source": "ebay",
        "raw_id": str(raw_id),
        "title": item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", ""),
        "price": converted["price"],
        "currency": converted["currency"],
        "source_price": converted.get("source_price"),
        "source_currency": converted.get("source_currency"),
        "sold_at": end_time,
        "url": item.get("viewItemURL", [None])[0] if isinstance(item.get("viewItemURL"), list) else item.get("viewItemURL"),
        "condition": condition_str,
        "image_url": image_url,
        "is_sold": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class EbayCaller:
    """Async eBay API caller for the marketplace aggregation agent."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.client_id = client_id or _CFG_EBAY_CLIENT_ID
        self.client_secret = client_secret or _CFG_EBAY_CLIENT_SECRET
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        marketplace_id: str = "EBAY_US",
    ) -> List[Dict[str, Any]]:
        """Search eBay Browse API for active listings.

        Returns a list of normalized MarketHit dicts.
        *marketplace_id* controls the X-EBAY-C-MARKETPLACE-ID header
        (e.g. ``EBAY_US``, ``EBAY_DE``, ``EBAY_JP``).
        """
        if not self.configured:
            logger.warning("[EbayCaller] Not configured (missing EBAY_CLIENT_ID/SECRET)")
            return []

        try:
            ebay_circuit.check()
        except CircuitOpenError:
            logger.warning("[EbayCaller] Circuit breaker OPEN — skipping search")
            return []

        # Fetch live FX rates once for this call
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        client = await self._get_client()
        try:
            token = await _get_access_token(client, self.client_id, self.client_secret)
        except httpx.HTTPError:
            ebay_circuit.record_failure()
            logger.error("[EbayCaller] OAuth token acquisition failed", exc_info=True)
            return []

        params = {
            "q": query,
            "limit": str(min(limit, 200)),
        }

        url = f"{EBAY_BROWSE_BASE}/item_summary/search"
        try:
            resp = await client.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "unknown")
                logger.warning("[EbayCaller] Rate limited (Retry-After: %s)", retry_after)
                ebay_circuit.record_failure()
                return []

            resp.raise_for_status()
            data = resp.json()
            items = data.get("itemSummaries", [])
            ebay_circuit.record_success()
            return [_normalize_browse_item(item, rates) for item in items]

        except httpx.HTTPStatusError as e:
            ebay_circuit.record_failure()
            logger.error("[EbayCaller] Browse API HTTP error: %d", e.response.status_code)
            return []
        except httpx.RequestError:
            ebay_circuit.record_failure()
            logger.error("[EbayCaller] Browse API request failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        marketplace_id: str = "EBAY_US",
    ) -> List[Dict[str, Any]]:
        """Search eBay Finding API for sold/completed items.

        Returns a list of normalized MarketHit dicts with is_sold=True.
        *marketplace_id* maps to the Finding API GLOBAL-ID param.
        """
        if not self.configured:
            logger.warning("[EbayCaller] Not configured (missing EBAY_CLIENT_ID/SECRET)")
            return []

        try:
            ebay_circuit.check()
        except CircuitOpenError:
            logger.warning("[EbayCaller] Circuit breaker OPEN — skipping sold_comps")
            return []

        # Fetch live FX rates once for this call
        try:
            from app.lib.fx_service import get_rates
            rates = await get_rates()
        except Exception:
            rates = None

        # Map marketplace ID to Finding API GLOBAL-ID
        _MARKETPLACE_TO_GLOBAL_ID = {
            "EBAY_US": "EBAY-US",
            "EBAY_DE": "EBAY-DE",
            "EBAY_GB": "EBAY-GB",
            "EBAY_JP": "EBAY-JP",
            "EBAY_AU": "EBAY-AU",
        }
        global_id = _MARKETPLACE_TO_GLOBAL_ID.get(marketplace_id, "EBAY-US")

        client = await self._get_client()
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": self.client_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "GLOBAL-ID": global_id,
            "keywords": query,
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
            "itemFilter(1).name": "ListingType",
            "itemFilter(1).value(0)": "FixedPrice",
            "itemFilter(1).value(1)": "AuctionWithBIN",
            "paginationInput.entriesPerPage": str(min(limit, 100)),
            "sortOrder": "EndTimeSoonest",
        }

        try:
            resp = await client.get(EBAY_FINDING_BASE, params=params)

            if resp.status_code == 429:
                logger.warning("[EbayCaller] Finding API rate limited")
                ebay_circuit.record_failure()
                return []

            resp.raise_for_status()
            data = resp.json()

            search_result = (
                data.get("findCompletedItemsResponse", [{}])[0]
                .get("searchResult", [{}])[0]
            )
            items = search_result.get("item", [])
            ebay_circuit.record_success()
            return [_normalize_finding_item(item, rates) for item in items]

        except httpx.HTTPStatusError as e:
            ebay_circuit.record_failure()
            logger.error("[EbayCaller] Finding API HTTP error: %d", e.response.status_code)
            return []
        except httpx.RequestError:
            ebay_circuit.record_failure()
            logger.error("[EbayCaller] Finding API request failed", exc_info=True)
            return []

    async def health_check(self) -> bool:
        """Check if eBay API is reachable and credentials are valid."""
        if not self.configured:
            return False
        try:
            results = await self.search("collectible", limit=1)
            return True  # if no exception, we're good
        except Exception:
            return False
