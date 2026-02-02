from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from services.collectors_merge.core.market_models import MarketHit

from .util import normalize_currency


def normalize_ebay_sold(raw: dict[str, Any]) -> MarketHit:
    """
    Normalize eBay Finding API / Browse API sold item response to MarketHit.

    Supports both Finding API (findCompletedItems) and Browse API (search) response structures.
    """
    # Handle both Finding API and Browse API response shapes
    selling_status = raw.get("sellingStatus", {})
    current_price = selling_status.get("currentPrice", {})

    # Price extraction (Finding API vs Browse API)
    if isinstance(current_price, dict):
        price = normalize_currency(current_price)
        currency = current_price.get("@currencyId") or current_price.get("currencyId", "USD")
    else:
        price = normalize_currency(current_price)
        currency = raw.get("price", {}).get("currency", "USD")

    # Shipping cost extraction
    shipping_info = raw.get("shippingInfo", {})
    shipping_cost = shipping_info.get("shippingServiceCost", {})
    shipping = normalize_currency(shipping_cost) if shipping_cost else None

    # Condition extraction (Finding API vs Browse API)
    condition_obj = raw.get("condition", {})
    if isinstance(condition_obj, dict):
        condition = condition_obj.get("conditionDisplayName") or condition_obj.get("condition")
    else:
        condition = condition_obj

    # Seller info extraction
    seller_info = raw.get("sellerInfo", {})
    seller_score = None
    if seller_info:
        try:
            seller_score = float(seller_info.get("positiveFeedbackPercent", 0))
        except (ValueError, TypeError):
            pass

    # Determine if graded based on title/condition
    title = raw.get("title", "")
    graded = any(
        term in title.upper()
        for term in ["PSA", "BGS", "CGC", "SGC", "GRADED", "GRADE"]
    )

    return MarketHit(
        provider="ebay",
        listing_id=str(raw.get("itemId") or raw.get("legacyItemId", "")),
        title=title,
        price=price,
        currency=currency,
        shipping=shipping,
        condition=condition,
        graded=graded,
        ended_at=raw.get("endTime") or raw.get("itemEndDate"),
        url=raw.get("viewItemURL") or raw.get("itemWebUrl"),
        seller_score=seller_score,
        features_json={
            "raw": raw,
            "bids": selling_status.get("bidCount"),
            "category_id": raw.get("primaryCategory", {}).get("categoryId"),
            "category_name": raw.get("primaryCategory", {}).get("categoryName"),
            "listing_type": raw.get("listingInfo", {}).get("listingType"),
        },
        normalized_key=None,
    )


def ingest_ebay_sold(rows: Iterable[dict[str, Any]]) -> list[MarketHit]:
    out = []
    for r in rows:
        try:
            out.append(normalize_ebay_sold(r))
        except Exception:
            continue
    return out
