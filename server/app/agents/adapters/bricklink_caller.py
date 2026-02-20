"""
BrickLink API caller for the Marketplace Aggregation Agent.

BrickLink is the largest LEGO marketplace worldwide. Provides comprehensive
set pricing, part inventories, and sold data.

API docs: https://www.bricklink.com/v3/api.page

Env vars:
    BRICKLINK_CONSUMER_KEY    - OAuth consumer key
    BRICKLINK_CONSUMER_SECRET - OAuth consumer secret
    BRICKLINK_TOKEN           - OAuth access token
    BRICKLINK_TOKEN_SECRET    - OAuth access token secret
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from app.config import (
    BRICKLINK_CONSUMER_KEY as _CFG_CK,
    BRICKLINK_CONSUMER_SECRET as _CFG_CS,
    BRICKLINK_TOKEN as _CFG_TK,
    BRICKLINK_TOKEN_SECRET as _CFG_TS,
)
from workers.circuit_breaker import bricklink_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BRICKLINK_BASE = "https://api.bricklink.com/api/store/v1"

SUPPORTED_CATEGORIES = ["lego"]

BRICKLINK_SOURCE_RELIABILITY = 0.90


# ---------------------------------------------------------------------------
# OAuth 1.0a signing
# ---------------------------------------------------------------------------

def _oauth_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
    params: Optional[Dict[str, str]] = None,
) -> str:
    """Build OAuth 1.0a Authorization header for BrickLink API."""
    import base64
    nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
    timestamp = str(int(time.time()))

    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp,
        "oauth_token": token,
        "oauth_version": "1.0",
    }

    # Combine OAuth params with query params for signing
    all_params = {**oauth_params}
    if params:
        all_params.update(params)

    # Build signature base string
    encoded_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(all_params.items())
    )
    base = f"{method.upper()}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(encoded_params, safe='')}"
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"

    sig = hmac.new(signing_key.encode(), base.encode(), hashlib.sha1).digest()
    signature = base64.b64encode(sig).decode()

    oauth_params["oauth_signature"] = signature
    header = ", ".join(f'{k}="{urllib.parse.quote(v, safe="")}"' for k, v in sorted(oauth_params.items()))
    return f"OAuth {header}"


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_item(item: Dict[str, Any], price_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize a BrickLink item into a standard MarketHit dict."""
    item_no = item.get("no", "")
    name = item.get("name", "Unknown")
    item_type = item.get("type", "SET")
    year = item.get("year_released")
    image = item.get("image_url") or item.get("thumbnail_url") or ""

    if image and not image.startswith("http"):
        image = f"https://img.bricklink.com/ItemImage/{item_type[0]}N/0/{item_no}.png"

    # Price data from price guide (if available)
    avg_price = 0.0
    min_price = 0.0
    max_price = 0.0
    qty_sold = 0

    if price_info:
        price_detail = price_info.get("price_detail", [])
        if price_detail:
            prices = [float(p.get("unit_price", 0)) for p in price_detail if p.get("unit_price")]
            if prices:
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
                qty_sold = len(prices)
        else:
            avg_price = float(price_info.get("avg_price", 0))
            min_price = float(price_info.get("min_price", 0))
            max_price = float(price_info.get("max_price", 0))
            qty_sold = int(price_info.get("total_quantity", 0))

    return {
        "source": "bricklink",
        "raw_id": f"bricklink-{item_no}",
        "title": f"{item_no} {name}",
        "price": avg_price,
        "price_low": min_price,
        "price_high": max_price,
        "currency": price_info.get("currency_code", "USD") if price_info else "USD",
        "source_price": avg_price,
        "source_currency": price_info.get("currency_code", "USD") if price_info else "USD",
        "url": f"https://www.bricklink.com/v2/catalog/catalogitem.page?S={item_no}" if item_type == "SET" else f"https://www.bricklink.com/v2/catalog/catalogitem.page?P={item_no}",
        "condition": None,
        "image_url": image,
        "is_sold": False,
        "set_number": item_no,
        "year": str(year) if year else None,
        "qty_sold": qty_sold,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class BrickLinkCaller:
    """Async BrickLink API caller for the marketplace aggregation agent."""

    def __init__(
        self,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        token: Optional[str] = None,
        token_secret: Optional[str] = None,
    ):
        self.consumer_key = consumer_key or _CFG_CK
        self.consumer_secret = consumer_secret or _CFG_CS
        self.token = token or _CFG_TK
        self.token_secret = token_secret or _CFG_TS
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.consumer_key and self.consumer_secret and self.token and self.token_secret)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def _get(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Make an authenticated GET request to the BrickLink API."""
        url = f"{BRICKLINK_BASE}{endpoint}"
        auth = _oauth_header(
            "GET", url,
            self.consumer_key, self.consumer_secret,
            self.token, self.token_secret,
            params,
        )

        client = await self._client()
        resp = await client.get(
            url,
            params=params,
            headers={"Authorization": auth, "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        meta = data.get("meta", {})
        if meta.get("code") != 200:
            logger.warning("BrickLink API error: %s", meta.get("message"))
            return None

        return data.get("data")

    async def search(
        self,
        query: str,
        category: str = "lego",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search BrickLink catalog for LEGO sets/parts."""
        if not self.configured:
            logger.debug("BrickLink not configured — skipping search")
            return []

        try:
            bricklink_circuit.check()
        except CircuitOpenError:
            logger.warning("BrickLink circuit open — skipping")
            return []

        # Determine if query is a set number (digits only or digits-digits)
        is_set_number = query.replace("-", "").replace(" ", "").isdigit()

        try:
            if is_set_number:
                # Direct set lookup
                set_no = query.strip().replace(" ", "-")
                if "-" not in set_no:
                    set_no = f"{set_no}-1"

                item_data = await self._get(f"/items/SET/{set_no}")
                bricklink_circuit.record_success()

                if item_data:
                    # Also get price guide
                    price_data = await self._get(f"/items/SET/{set_no}/price", {"guide_type": "sold", "new_or_used": "N"})
                    return [_normalize_item(item_data, price_data)]
                return []
            else:
                # For text searches, BrickLink API doesn't have a search endpoint
                # Return empty — Firecrawl/Crawl4AI handles BrickLink text search
                logger.debug("BrickLink text search not supported via API — use set number")
                return []

        except Exception as exc:
            bricklink_circuit.record_failure()
            logger.warning("BrickLink search error: %s", exc)
            return []

    async def get_price_guide(
        self,
        set_no: str,
        new_or_used: str = "N",
        guide_type: str = "sold",
    ) -> Optional[Dict[str, Any]]:
        """Get price guide for a specific LEGO set."""
        if not self.configured:
            return None

        try:
            bricklink_circuit.check()
        except CircuitOpenError:
            return None

        if "-" not in set_no:
            set_no = f"{set_no}-1"

        try:
            data = await self._get(
                f"/items/SET/{set_no}/price",
                {"guide_type": guide_type, "new_or_used": new_or_used},
            )
            bricklink_circuit.record_success()
            return data

        except Exception as exc:
            bricklink_circuit.record_failure()
            logger.warning("BrickLink price guide error: %s", exc)
            return None

    async def sold_comps(
        self,
        query: str,
        category: str = "lego",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Get sold price data from BrickLink."""
        results = await self.search(query, category, limit)
        for r in results:
            r["is_sold"] = True
        return results

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            data = await self._get("/colors")
            return data is not None
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
