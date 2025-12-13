from __future__ import annotations

from typing import Any

from .client import BrickLinkClient


# NOTE: Placeholder: map to BrickLink Price Guide response
def price_guide(set_no: str) -> dict[str, Any]:
    bl = BrickLinkClient()
    # Example: /priceguide/part (change to appropriate set endpoint)
    # resp = bl.get(f"/priceguide/set/{set_no}", params={"new_or_used":"N","guide_type":"sold"})
    # return resp
    return {"ok": False, "note": "wire actual BrickLink endpoint for set price guide"}
