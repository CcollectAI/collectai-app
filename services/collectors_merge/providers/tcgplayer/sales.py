from __future__ import annotations

from typing import Any

from .client import TCGClient


# Placeholder: wire exact endpoints (pricing/sales history)
def recent_sales(product_id: int, days: int = 30) -> list[dict[str, Any]]:
    tcg = TCGClient()
    # Example placeholder path:
    # js = tcg.get(f"/pricing/product/{product_id}", params={"days": days})
    return []
