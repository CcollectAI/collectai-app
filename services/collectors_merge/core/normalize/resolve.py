from __future__ import annotations

import re

SET_RE = re.compile(r"\b(\d{4,5})\b")
SKU_RE = re.compile(r"\b([A-Z0-9]{2,6}-?[A-Z0-9]{2,8})\b", re.I)


def candidates_from_text(text: str, category: str) -> list[str]:
    text = (text or "").strip()
    cat = (category or "misc").lower()
    cands: list[str] = []
    if cat == "lego":
        m = SET_RE.search(text)
        if m:
            set_no = m.group(1)
            # we don't know pieces/ret/sealed, leave placeholders
            cands.append(f"lego|{set_no}|pcs:?|ret:0|s:0")
            cands.append(f"lego|{set_no}|pcs:?|ret:1|s:1")
    else:
        m = SKU_RE.search(text)
        if m:
            sku = m.group(1).upper()
            cands.append(f"{cat}|sku:{sku}")
    if not cands:
        cands.append(f"{cat}|fallback")
    # keep unique order
    seen = set()
    out = []
    for k in cands:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out
