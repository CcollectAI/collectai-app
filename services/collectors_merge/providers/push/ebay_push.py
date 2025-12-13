from __future__ import annotations

from typing import Any


# Placeholder: use eBay Sell Inventory/Account APIs to create drafts where supported.
def create_draft_ebay(listing: dict[str, Any]) -> dict[str, Any]:
    # listing: {title, body, price, images[], category_hint}
    # TODO: map to eBay Sell API payload; return draft_id or link
    return {"ok": False, "note": "Wire eBay Sell API to create drafts"}
