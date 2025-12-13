from __future__ import annotations

from typing import Any


def normalized_key(category: str, attrs: dict[str, Any]) -> str:
    c = (category or "misc").lower()
    if c == "lego" and attrs.get("set_no"):
        pcs = attrs.get("piece_count") or "?"
        ret = 1 if attrs.get("retired") else 0
        s = 1 if attrs.get("sealed") else 0
        return f"lego|{attrs['set_no']}|pcs:{pcs}|ret:{ret}|s:{s}"
    if c in ("tcg", "card") and attrs.get("psa_cert"):
        g = attrs.get("grade") or "?"
        return f"tcg|psa:{attrs['psa_cert']}|g:{g}"
    if attrs.get("sku"):
        return f"{c}|sku:{attrs['sku']}"
    return f"{c}|fallback"
