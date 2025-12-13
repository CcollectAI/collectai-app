from __future__ import annotations

from typing import Any

from .client import EbayClient


# NOTE: Replace with the exact eBay API & query (Browse API doesn't expose sold; use Finding / Sell Analytics or third-party if needed).
# Here we show a placeholder to search items and assume 'price' & 'endTime'-like fields are available.
def fetch_recent(query: str, limit: int = 50) -> list[dict[str, Any]]:
    eb = EbayClient()
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    js = eb.get(url, params={"q": query, "limit": str(limit)})
    return js.get("itemSummaries", [])
