from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from services.collectors_merge.core.market_models import MarketHit

from .util import normalize_currency


def normalize_ebay_sold(raw: dict[str, Any]) -> MarketHit:
    # TODO: map actual eBay API fields
    return MarketHit(
        provider="ebay",
        listing_id=str(raw.get("itemId")),
        title=raw.get("title"),
        price=normalize_currency(raw.get("sellingStatus", {}).get("currentPrice")),
        currency=raw.get("sellingStatus", {})
        .get("currentPrice", {})
        .get("@currencyId", "USD"),
        shipping=None,
        condition=raw.get("condition", {}).get("conditionDisplayName"),
        graded=None,
        ended_at=raw.get("endTime"),
        url=raw.get("viewItemURL"),
        seller_score=None,
        features_json={"raw": raw},
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
