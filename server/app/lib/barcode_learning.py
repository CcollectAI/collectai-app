"""
Barcodes learned from what members save (2026-09-26).

WHY: the catalogue has no barcodes and the free lookups cover ISBNs only, so a
LEGO box or a Funko Pop never resolved — and Merle ruled out a paid EAN source.
Every save that came from a scan now records what the code turned out to be
(`record_observation`), and the barcode cascade asks here after the catalogue
(`lookup_learned`, called from intake/field_extraction.py).

WHAT MAY BE SHOWN TO WHOM — the one rule that matters here:
  * A CATALOGUE-linked answer (canonical_key set) may be shown to anyone: it
    names a public catalogue row, never a member's own words. The key is
    resolved by the server from the saved title — never taken from a client.
  * A free-typed answer (no catalogue link) is the member's OWN wording. It is
    shown back to that member, and to others only once TWO different members
    have saved the same (category, title) for the code — one person's text
    never reaches another person alone.
Ties go to the answer with more members behind it, then the most recent.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MIN_MEMBERS_FOR_FREE_TEXT = 2

# Only PRODUCT codes are learned: EAN-8, UPC-A (12), EAN-13, GTIN-14. The
# shared validator also accepts Code 128 & co. — often a per-item SERIAL
# number, which names one physical object, not a product: pointless to share
# and possibly personal.
_PRODUCT_CODE = re.compile(r"^(\d{8}|\d{12,14})$")


def _norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", "", (title or "").lower())).strip()


async def record_observation(
    conn,
    user_id: str,
    barcode: Optional[str],
    title: Optional[str],
    category: Optional[str],
    canonical_key: Optional[str],
) -> bool:
    """Upsert this member's answer for the barcode. Never raises; False = not recorded."""
    code = (barcode or "").strip()
    name = (title or "").strip()
    if not code or not name:
        return False
    if not _PRODUCT_CODE.match(code):
        return False
    try:
        await conn.execute(
            """
            INSERT INTO public.barcode_observations
                (barcode, user_id, category, title, canonical_key)
            VALUES ($1, $2::uuid, $3, $4, $5)
            ON CONFLICT (barcode, user_id) DO UPDATE
               SET category = EXCLUDED.category,
                   title = EXCLUDED.title,
                   canonical_key = EXCLUDED.canonical_key,
                   updated_at = now()
            """,
            code, user_id, category, name[:500], canonical_key,
        )
        return True
    except Exception as e:
        # WARNING, not debug: a learning write that silently stops is the
        # "feature quietly dead" class (learning_silent_fallbacks_hide_dead_features).
        logger.warning("[barcode_learning] record failed for %s: %s", code, e)
        return False


async def lookup_learned(conn, barcode: str, user_id: Optional[str]) -> Optional[dict[str, Any]]:
    """The best learned answer this member may see, or None."""
    if not _PRODUCT_CODE.match((barcode or "").strip()):
        return None
    rows = await conn.fetch(
        """
        SELECT user_id::text AS user_id, category, title, canonical_key, updated_at
        FROM public.barcode_observations
        WHERE barcode = $1
        """,
        barcode.strip(),
    )
    if not rows:
        return None

    # 1. Catalogue-linked answers: public data, count members per (category, key).
    linked: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        if r["canonical_key"] and r["category"]:
            k = (r["category"], r["canonical_key"])
            e = linked.setdefault(k, {"members": 0, "latest": r["updated_at"], "title": r["title"]})
            e["members"] += 1
            if r["updated_at"] > e["latest"]:
                e["latest"], e["title"] = r["updated_at"], r["title"]
    if linked:
        (category, key), e = max(linked.items(), key=lambda kv: (kv[1]["members"], kv[1]["latest"]))
        return {"category": category, "canonical_key": key, "title": e["title"],
                "members": e["members"], "source": "learned_catalogue"}

    # 2. Free text: the member's own answer first …
    if user_id:
        own = [r for r in rows if r["user_id"] == user_id]
        if own:
            r = own[0]
            return {"category": r["category"], "canonical_key": None, "title": r["title"],
                    "members": 1, "source": "learned_own"}

    # … others' only when enough different members agree.
    groups: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        k = (r["category"], _norm_title(r["title"]))
        e = groups.setdefault(k, {"members": 0, "latest": r["updated_at"], "title": r["title"]})
        e["members"] += 1
        if r["updated_at"] > e["latest"]:
            e["latest"], e["title"] = r["updated_at"], r["title"]
    agreed = {k: e for k, e in groups.items() if e["members"] >= _MIN_MEMBERS_FOR_FREE_TEXT}
    if not agreed:
        return None
    (category, _), e = max(agreed.items(), key=lambda kv: (kv[1]["members"], kv[1]["latest"]))
    return {"category": category, "canonical_key": None, "title": e["title"],
            "members": e["members"], "source": "learned_agreed"}
