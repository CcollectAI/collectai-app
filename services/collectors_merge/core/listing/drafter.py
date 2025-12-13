from __future__ import annotations

from typing import Any


def map_condition(cond: str) -> str:
    if not cond:
        return "Used"
    c = cond.strip().lower()
    mapping = {
        "new": "New",
        "sealed": "New (Sealed)",
        "like new": "Used - Like New",
        "ln": "Used - Like New",
        "very good": "Used - Very Good",
        "vg": "Used - Very Good",
        "good": "Used - Good",
        "g": "Used - Good",
    }
    return mapping.get(c, cond)


def draft_title(category: str, attrs: dict[str, Any]) -> str:
    c = (category or "").lower()
    if c in ("lego",):
        parts = [
            attrs.get("set_no"),
            attrs.get("title") or attrs.get("theme"),
            "LEGO Set",
        ]
        if attrs.get("sealed"):
            parts.append("Sealed")
        if attrs.get("retired"):
            parts.append("Retired")
        return " | ".join([p for p in parts if p])
    if c in ("gunpla", "model_kits"):
        parts = [
            attrs.get("grade_code"),
            attrs.get("scale"),
            attrs.get("title") or "Gunpla",
        ]
        if attrs.get("limited"):
            parts.append("Premium/Exclusive")
        if attrs.get("sealed"):
            parts.append("Sealed")
        return " ".join([p for p in parts if p])
    if c in ("warhammer", "wh", "warhammer_40k"):
        parts = [attrs.get("faction"), attrs.get("unit"), "Warhammer"]
        if attrs.get("paint_quality") is not None:
            parts.append(f"Paint {attrs.get('paint_quality')}/5")
        if attrs.get("sealed_sprue"):
            parts.append("NOS/Sealed Sprue")
        return " ".join([p for p in parts if p])
    if c in ("diecast",):
        parts = [
            attrs.get("scale"),
            attrs.get("casting"),
            attrs.get("series"),
            "Diecast",
        ]
        if attrs.get("chase_variant"):
            parts.append("Chase")
        return " ".join([p for p in parts if p])
    # TCG & Designer toys default
    parts = [attrs.get("set"), attrs.get("card_no"), attrs.get("title")]
    if attrs.get("grade"):
        parts.append(attrs.get("grade"))
    return " | ".join([p for p in parts if p])


def draft_body(category: str, attrs: dict[str, Any]) -> str:
    cond = map_condition(
        attrs.get("condition") or ("New" if attrs.get("sealed") else "Used")
    )
    lines = [
        f"Condition: {cond}",
        f"Category: {category}",
    ]
    if attrs.get("grade"):
        lines.append(
            f"Graded: {attrs.get('grade')}"
            + (f" ({attrs.get('graded_by')})" if attrs.get("graded_by") else "")
        )
    if attrs.get("sealed"):
        lines.append("Sealed: Yes")
    # category specifics
    c = (category or "").lower()
    if c in ("lego",):
        if attrs.get("retired") is not None:
            lines.append(f"Retired: {'Yes' if attrs.get('retired') else 'No'}")
        if attrs.get("piece_count"):
            lines.append(f"Pieces: {attrs.get('piece_count')}")
        if attrs.get("set_no"):
            lines.append(f"Set No.: {attrs.get('set_no')}")
    if c in ("gunpla", "model_kits"):
        if attrs.get("grade_code"):
            lines.append(f"Grade: {attrs.get('grade_code')}")
        if attrs.get("scale"):
            lines.append(f"Scale: {attrs.get('scale')}")
        if attrs.get("limited"):
            lines.append("Exclusive: Yes")
    if c in ("warhammer", "wh", "warhammer_40k"):
        if attrs.get("faction"):
            lines.append(f"Faction: {attrs.get('faction')}")
        if attrs.get("unit"):
            lines.append(f"Unit: {attrs.get('unit')}")
        if attrs.get("sealed_sprue"):
            lines.append("Sealed Sprue: Yes")
        if attrs.get("paint_quality") is not None:
            lines.append(f"Paint Quality: {attrs.get('paint_quality')}/5")
    if c in ("diecast",):
        if attrs.get("scale"):
            lines.append(f"Scale: {attrs.get('scale')}")
        if attrs.get("series"):
            lines.append(f"Series: {attrs.get('series')}")
        if attrs.get("casting"):
            lines.append(f"Casting: {attrs.get('casting')}")
        if attrs.get("chase_variant"):
            lines.append("Chase Variant: Yes")
    body = "\n".join(lines) + "\n\nShipped with care. Questions welcome."
    return body


def price_suggestion(q50: float, buffer_pct: float = 0.08) -> float:
    try:
        return round(float(q50) * (1 + buffer_pct), 2)
    except Exception:
        return None


def draft_listing(
    category: str,
    attrs: dict[str, Any],
    last_pred: dict[str, float] | None = None,
    buffer_pct: float = 0.08,
):
    title = draft_title(category, attrs)
    body = draft_body(category, attrs)
    ask = price_suggestion((last_pred or {}).get("q50"), buffer_pct)
    return {"title": title, "body": body, "suggested_price": ask}
