from __future__ import annotations

import os
from typing import Any

import httpx

# eBay Sell API endpoints
# Note: Requires user OAuth token (not client_credentials) with sell scope
EBAY_SELL_INVENTORY_API = "https://api.ebay.com/sell/inventory/v1"
EBAY_SANDBOX_SELL_API = "https://api.sandbox.ebay.com/sell/inventory/v1"


def _get_sell_api_base() -> str:
    """Return sandbox or production URL based on environment."""
    if os.getenv("EBAY_SANDBOX", "false").lower() == "true":
        return EBAY_SANDBOX_SELL_API
    return EBAY_SELL_INVENTORY_API


def _map_condition_to_ebay(condition: str | None) -> str:
    """Map internal condition to eBay condition enum."""
    mapping = {
        "mint": "NEW",
        "nm": "LIKE_NEW",
        "near mint": "LIKE_NEW",
        "excellent": "VERY_GOOD",
        "good": "GOOD",
        "fair": "ACCEPTABLE",
        "poor": "FOR_PARTS_OR_NOT_WORKING",
    }
    return mapping.get((condition or "").lower(), "USED_EXCELLENT")


def create_draft_ebay(listing: dict[str, Any]) -> dict[str, Any]:
    """
    Create an eBay listing draft via the Sell Inventory API.

    Args:
        listing: {title, body, price, images[], category_hint, condition, currency}

    Returns:
        {ok: bool, draft_id?: str, offer_id?: str, error?: str}

    Note: Requires EBAY_USER_OAUTH_TOKEN with 'https://api.ebay.com/oauth/api_scope/sell.inventory' scope.
    This is a user-specific token obtained via OAuth consent flow, not client_credentials.
    """
    user_token = os.getenv("EBAY_USER_OAUTH_TOKEN")
    if not user_token:
        return {
            "ok": False,
            "error": "EBAY_USER_OAUTH_TOKEN not configured",
            "note": "eBay Sell API requires user OAuth token with sell.inventory scope",
        }

    base_url = _get_sell_api_base()

    # Build inventory item payload
    # See: https://developer.ebay.com/api-docs/sell/inventory/resources/inventory_item/methods/createOrReplaceInventoryItem
    sku = listing.get("sku") or f"COLL-{listing.get('item_id', 'DRAFT')}"
    inventory_payload = {
        "product": {
            "title": listing.get("title", "Collectible Item"),
            "description": listing.get("body", ""),
            "imageUrls": listing.get("images", []),
        },
        "condition": _map_condition_to_ebay(listing.get("condition")),
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 1,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": "en-US",
    }

    try:
        with httpx.Client(timeout=30) as client:
            # Step 1: Create/update inventory item
            resp = client.put(
                f"{base_url}/inventory_item/{sku}",
                headers=headers,
                json=inventory_payload,
            )
            if resp.status_code not in (200, 201, 204):
                return {
                    "ok": False,
                    "error": f"Failed to create inventory item: {resp.status_code}",
                    "detail": resp.text[:500],
                }

            # Step 2: Create offer (draft listing)
            offer_payload = {
                "sku": sku,
                "marketplaceId": listing.get("marketplace", "EBAY_US"),
                "format": "FIXED_PRICE",
                "pricingSummary": {
                    "price": {
                        "value": str(listing.get("price", 0)),
                        "currency": listing.get("currency", "USD"),
                    }
                },
                "listingDescription": listing.get("body", ""),
                "availableQuantity": 1,
            }

            resp = client.post(
                f"{base_url}/offer",
                headers=headers,
                json=offer_payload,
            )
            if resp.status_code not in (200, 201):
                return {
                    "ok": False,
                    "error": f"Failed to create offer: {resp.status_code}",
                    "detail": resp.text[:500],
                    "sku": sku,
                }

            offer_data = resp.json()
            return {
                "ok": True,
                "draft_id": sku,
                "offer_id": offer_data.get("offerId"),
                "note": "Draft created. Publish via publishOffer endpoint when ready.",
            }

    except httpx.RequestError as e:
        return {"ok": False, "error": f"Network error: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
