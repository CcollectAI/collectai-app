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

from app.config import USD_TO_EUR, EBAY_CLIENT_ID as _CFG_EBAY_CLIENT_ID, EBAY_CLIENT_SECRET as _CFG_EBAY_CLIENT_SECRET

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

def _convert_price(price: float, currency: str) -> Dict[str, Any]:
    upper = currency.upper()
    if upper == "EUR":
        return {"price": price, "currency": "EUR"}
    if upper == "USD":
        return {"price": round(price * USD_TO_EUR, 2), "currency": "EUR"}
    return {"price": price, "currency": upper}


def _normalize_browse_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an eBay Browse API item summary to a MarketHit dict."""
    raw_price = float(item.get("price", {}).get("value", 0) or 0)
    raw_currency = item.get("price", {}).get("currency", "USD")
    converted = _convert_price(raw_price, raw_currency)
    raw_id = item.get("itemId", "")

    return {
        "source": "ebay",
        "raw_id": str(raw_id),
        "title": item.get("title", ""),
        "price": converted["price"],
        "currency": converted["currency"],
        "sold_at": None,
        "url": item.get("itemWebUrl") or item.get("itemHref"),
        "condition": item.get("condition") or item.get("conditionId"),
        "image_url": (item.get("image") or {}).get("imageUrl"),
        "is_sold": False,
    }


def _normalize_finding_item(item: Dict[str, Any]) -> Dict[str, Any]:
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

    converted = _convert_price(raw_price, raw_currency)
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
    ) -> List[Dict[str, Any]]:
        """Search eBay Browse API for active listings.

        Returns a list of normalized MarketHit dicts.
        """
        if not self.configured:
            logger.warning("[EbayCaller] Not configured (missing EBAY_CLIENT_ID/SECRET)")
            return []

        client = await self._get_client()
        try:
            token = await _get_access_token(client, self.client_id, self.client_secret)
        except Exception:
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
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "unknown")
                logger.warning("[EbayCaller] Rate limited (Retry-After: %s)", retry_after)
                return []

            resp.raise_for_status()
            data = resp.json()
            items = data.get("itemSummaries", [])
            return [_normalize_browse_item(item) for item in items]

        except httpx.HTTPStatusError as e:
            logger.error("[EbayCaller] Browse API HTTP error: %d", e.response.status_code)
            return []
        except Exception:
            logger.error("[EbayCaller] Browse API request failed", exc_info=True)
            return []

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search eBay Finding API for sold/completed items.

        Returns a list of normalized MarketHit dicts with is_sold=True.
        """
        if not self.configured:
            logger.warning("[EbayCaller] Not configured (missing EBAY_CLIENT_ID/SECRET)")
            return []

        client = await self._get_client()
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": self.client_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
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
                return []

            resp.raise_for_status()
            data = resp.json()

            search_result = (
                data.get("findCompletedItemsResponse", [{}])[0]
                .get("searchResult", [{}])[0]
            )
            items = search_result.get("item", [])
            return [_normalize_finding_item(item) for item in items]

        except httpx.HTTPStatusError as e:
            logger.error("[EbayCaller] Finding API HTTP error: %d", e.response.status_code)
            return []
        except Exception:
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
