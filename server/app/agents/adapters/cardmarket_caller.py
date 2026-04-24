"""
Cardmarket API caller for the Marketplace Aggregation Agent.

Cardmarket is the #1 European marketplace for TCG products (Pokemon, MTG,
Yu-Gi-Oh!, Lorcana). Uses the Cardmarket API v2.0 with OAuth 1.0a.

Env vars:
    CARDMARKET_APP_TOKEN   - Cardmarket API application token
    CARDMARKET_APP_SECRET  - Cardmarket API application secret
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from app.config import (
    CARDMARKET_APP_TOKEN as _CFG_TOKEN,
    CARDMARKET_APP_SECRET as _CFG_SECRET,
)
from workers.circuit_breaker import cardmarket_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CARDMARKET_BASE = "https://api.cardmarket.com/ws/v2.0"

# Cardmarket game IDs for CollectAI's TCG categories
CATEGORY_TO_GAME_ID: Dict[str, int] = {
    "pokemon": 6,
    "mtg": 1,
    "yugioh": 3,
    "lorcana": 9,
}

SUPPORTED_CATEGORIES = list(CATEGORY_TO_GAME_ID.keys())

# Source reliability for provenance scoring
CARDMARKET_SOURCE_RELIABILITY = 0.85


# ---------------------------------------------------------------------------
# OAuth 1.0a signing
# ---------------------------------------------------------------------------

def _oauth_header(method: str, url: str, app_token: str, app_secret: str) -> str:
    """Build OAuth 1.0a Authorization header (application-only, no user token)."""
    nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
    timestamp = str(int(time.time()))

    params = {
        "oauth_consumer_key": app_token,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": timestamp,
        "oauth_version": "1.0",
    }

    # Build signature base string
    encoded_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(params.items())
    )
    base = f"{method.upper()}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(encoded_params, safe='')}"
    signing_key = f"{urllib.parse.quote(app_secret, safe='')}&"

    sig = hmac.new(signing_key.encode(), base.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(sig).decode()

    params["oauth_signature"] = signature
    header = ", ".join(f'{k}="{urllib.parse.quote(v, safe="")}"' for k, v in sorted(params.items()))
    return f"OAuth {header}"


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_product(product: Dict[str, Any], category: str) -> Dict[str, Any]:
    """Normalize a Cardmarket product into a standard MarketHit dict."""
    price_guide = product.get("priceGuide", {})
    name = product.get("enName") or product.get("locName") or "Unknown"
    image = product.get("image") or ""
    if image and not image.startswith("http"):
        image = f"https://static.cardmarket.com/img/items/{image}"

    # Per-listing attributes for attribute_aggregation_worker. Cardmarket
    # TREND prices aggregate across all conditions/languages so we can't
    # capture condition here — but rarity/expansion/number are per-card
    # and feed the aggregated catalog attributes downstream.
    attrs: Dict[str, Any] = {}
    if product.get("rarity"):
        attrs["rarity"] = product["rarity"]
    exp_name = (product.get("expansion") or {}).get("enName")
    if exp_name:
        attrs["set_name"] = exp_name
    if product.get("number"):
        attrs["card_number"] = str(product["number"])

    return {
        "source": "cardmarket",
        "raw_id": f"cardmarket-{product.get('idProduct', '')}",
        "title": name,
        "price": price_guide.get("TREND", 0),
        "price_low": price_guide.get("LOW", 0),
        "price_avg": price_guide.get("AVG", 0),
        "currency": "EUR",
        "source_price": price_guide.get("TREND", 0),
        "source_currency": "EUR",
        "url": f"https://www.cardmarket.com/en/{'Pokemon' if category == 'pokemon' else 'Magic' if category == 'mtg' else 'YuGiOh' if category == 'yugioh' else 'Lorcana'}/Products/Singles/{urllib.parse.quote(name)}",
        "condition": None,
        "image_url": image,
        "is_sold": False,
        "quantity_available": product.get("countArticles", None),
        "rarity": product.get("rarity") or None,
        "expansion": product.get("expansion", {}).get("enName") or None,
        "attributes": attrs,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CardmarketCaller:
    """Async Cardmarket API caller for the marketplace aggregation agent."""

    def __init__(
        self,
        app_token: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        self.app_token = app_token or _CFG_TOKEN
        self.app_secret = app_secret or _CFG_SECRET
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(self.app_token and self.app_secret)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def search(
        self,
        query: str,
        category: str = "pokemon",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search Cardmarket for products matching a query."""
        if not self.configured:
            logger.debug("Cardmarket not configured — skipping search")
            return []

        game_id = CATEGORY_TO_GAME_ID.get(category)
        if game_id is None:
            return []

        try:
            cardmarket_circuit.check()
        except CircuitOpenError:
            logger.warning("Cardmarket circuit open — skipping")
            return []

        url = f"{CARDMARKET_BASE}/products/find"
        params = {
            "search": query,
            "idGame": str(game_id),
            "maxResults": str(min(limit, 100)),
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        try:
            client = await self._client()
            auth_header = _oauth_header("GET", full_url, self.app_token, self.app_secret)
            resp = await client.get(
                full_url,
                headers={"Authorization": auth_header, "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            cardmarket_circuit.record_success()

            products = data.get("product", [])
            if isinstance(products, dict):
                products = [products]

            return [_normalize_product(p, category) for p in products[:limit]]

        except Exception as exc:
            cardmarket_circuit.record_failure()
            logger.warning("Cardmarket search error: %s", exc)
            return []

    async def sold_comps(
        self,
        query: str,
        category: str = "pokemon",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Get price guide data (Cardmarket doesn't expose sold listings directly,
        but priceGuide contains AVG/LOW/TREND from recent sales)."""
        results = await self.search(query, category, limit)
        for r in results:
            r["is_sold"] = True
        return results

    async def health_check(self) -> bool:
        """Check if the Cardmarket API is reachable."""
        if not self.configured:
            return False
        try:
            client = await self._client()
            url = f"{CARDMARKET_BASE}/games"
            auth_header = _oauth_header("GET", url, self.app_token, self.app_secret)
            resp = await client.get(
                url,
                headers={"Authorization": auth_header, "Accept": "application/json"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
