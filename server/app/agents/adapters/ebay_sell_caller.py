"""eBay Sell API caller — user-delegated OAuth + minimal listing flow.

Distinct from `ebay_caller.py` which uses the Client-Credentials flow for
read-only Browse API. Selling requires user-delegated tokens via the
Authorization-Code flow.

Flow:
  1. User clicks "Connect eBay" → /marketplace/listings/oauth/ebay/start
     redirects to eBay's auth page with our scopes.
  2. eBay redirects user back to our callback with `?code=...`.
  3. Backend exchanges code → access_token (~2h) + refresh_token (~18mo).
  4. Tokens stored in marketplace_listings_accounts.{oauth_token_enc,
     refresh_token_enc, token_expires_at}. Currently stored plaintext —
     follow-up to encrypt with Supabase Vault.
  5. To list an item: refresh token if near expiry → create inventory_item
     → create offer → publish offer. Returns the eBay item ID.

Env vars required:
  EBAY_CLIENT_ID, EBAY_CLIENT_SECRET (already set)
  EBAY_REDIRECT_URI — RuName for OAuth callback (must be registered in
                      the eBay dev console, exact-match)
  EBAY_SELL_SCOPES — space-separated, defaults to inventory+account
"""
from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Production endpoints — sandbox uses different hosts.
EBAY_AUTH_BASE = "https://auth.ebay.com/oauth2/authorize"
EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_API_BASE = "https://api.ebay.com"

# Default scopes cover inventory + offer + account. Add fulfillment when
# we wire shipping policies + order management.
DEFAULT_SCOPES = " ".join([
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
])

# Refresh-token-near-expiry threshold — refresh proactively if access
# token has < 5 minutes of life left.
REFRESH_BUFFER = timedelta(minutes=5)


def _basic_auth_header() -> str:
    cid = os.environ["EBAY_CLIENT_ID"]
    sec = os.environ["EBAY_CLIENT_SECRET"]
    creds = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    return f"Basic {creds}"


def build_oauth_url(state: str) -> str:
    """Construct the eBay user-consent URL. Caller passes a CSRF state
    token they should validate on callback."""
    redirect = os.environ.get("EBAY_REDIRECT_URI", "")
    scopes = os.environ.get("EBAY_SELL_SCOPES", DEFAULT_SCOPES)
    if not redirect:
        raise RuntimeError("EBAY_REDIRECT_URI not set — register a RuName in eBay dev console")
    return (
        f"{EBAY_AUTH_BASE}?client_id={quote(os.environ['EBAY_CLIENT_ID'])}"
        f"&response_type=code"
        f"&redirect_uri={quote(redirect)}"
        f"&scope={quote(scopes)}"
        f"&state={quote(state)}"
    )


async def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Trade an authorization code for access + refresh tokens.

    Returns {access_token, refresh_token, expires_at, refresh_expires_at}.
    """
    redirect = os.environ.get("EBAY_REDIRECT_URI", "")
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            EBAY_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect,
            },
        )
    resp.raise_for_status()
    data = resp.json()
    now = datetime.now(timezone.utc)
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": now + timedelta(seconds=int(data.get("expires_in", 7200))),
        "refresh_expires_at": now + timedelta(seconds=int(data.get("refresh_token_expires_in", 47304000))),
    }


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Use a refresh token to get a fresh access token. Returns the same
    shape as exchange_code_for_token (refresh_token unchanged)."""
    scopes = os.environ.get("EBAY_SELL_SCOPES", DEFAULT_SCOPES)
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            EBAY_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": scopes,
            },
        )
    resp.raise_for_status()
    data = resp.json()
    now = datetime.now(timezone.utc)
    return {
        "access_token": data["access_token"],
        "refresh_token": refresh_token,
        "expires_at": now + timedelta(seconds=int(data.get("expires_in", 7200))),
    }


async def ensure_fresh_token(account: Dict[str, Any]) -> str:
    """Return a usable access token, refreshing if near-expiry.

    `account` is a row dict from `marketplace_listings_accounts` with
    fields oauth_token_enc / refresh_token_enc / token_expires_at.
    Caller is responsible for persisting the refreshed token back to DB.
    """
    expires_at = account.get("token_expires_at")
    if expires_at and (expires_at - datetime.now(timezone.utc)) > REFRESH_BUFFER:
        return account["oauth_token_enc"]
    refreshed = await refresh_access_token(account["refresh_token_enc"])
    return refreshed["access_token"]


# ---------------------------------------------------------------------------
# Inventory + Offer + Publish — minimal happy path. Full flow per
# https://developer.ebay.com/api-docs/sell/inventory/static/overview.html
# ---------------------------------------------------------------------------


async def create_inventory_item(
    access_token: str, sku: str, item: Dict[str, Any],
) -> None:
    """PUT /sell/inventory/v1/inventory_item/{sku}.

    `item` must include: title, description, condition, image_urls,
    aspects (brand/model/etc), package_weight_oz."""
    url = f"{EBAY_API_BASE}/sell/inventory/v1/inventory_item/{quote(sku)}"
    body = {
        "product": {
            "title": item["title"][:80],
            "description": item.get("description", item["title"])[:4000],
            "imageUrls": item.get("image_urls", [])[:12],
            "aspects": item.get("aspects", {}),
        },
        "condition": item.get("condition", "USED_EXCELLENT"),
        "availability": {
            "shipToLocationAvailability": {
                "quantity": int(item.get("quantity", 1)),
            },
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
        )
    resp.raise_for_status()


async def create_offer(
    access_token: str, sku: str, item: Dict[str, Any],
) -> str:
    """POST /sell/inventory/v1/offer. Returns the offer_id."""
    url = f"{EBAY_API_BASE}/sell/inventory/v1/offer"
    body = {
        "sku": sku,
        "marketplaceId": item.get("marketplace_id", "EBAY_US"),
        "format": "FIXED_PRICE",
        "availableQuantity": int(item.get("quantity", 1)),
        "categoryId": item.get("category_id", ""),
        "pricingSummary": {
            "price": {
                "value": str(item["price"]),
                "currency": item.get("currency", "USD"),
            },
        },
        "merchantLocationKey": item.get("location_key", "default"),
        "listingPolicies": {
            "fulfillmentPolicyId": item.get("fulfillment_policy_id", ""),
            "paymentPolicyId":      item.get("payment_policy_id", ""),
            "returnPolicyId":       item.get("return_policy_id", ""),
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
        )
    resp.raise_for_status()
    return resp.json()["offerId"]


async def publish_offer(access_token: str, offer_id: str) -> str:
    """POST /sell/inventory/v1/offer/{offer_id}/publish.

    Returns the eBay listing_id (legacy item_id)."""
    url = f"{EBAY_API_BASE}/sell/inventory/v1/offer/{quote(offer_id)}/publish"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
        )
    resp.raise_for_status()
    return resp.json().get("listingId", "")


async def publish_to_ebay(
    account: Dict[str, Any], sku: str, item: Dict[str, Any],
) -> Dict[str, Any]:
    """Full happy-path publish: refresh → inventory_item → offer → publish.

    Returns {ebay_listing_id, sku, offer_id}.
    Caller wraps in try/except and updates marketplace_listings.status.
    """
    access_token = await ensure_fresh_token(account)
    await create_inventory_item(access_token, sku, item)
    offer_id = await create_offer(access_token, sku, item)
    listing_id = await publish_offer(access_token, offer_id)
    return {"ebay_listing_id": listing_id, "sku": sku, "offer_id": offer_id}
