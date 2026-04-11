"""
Notes Parser — convert pipe-delimited free-text `notes` field into
structured `attributes_json` per category.

Most catalog seeds dump rich product details into a free-text `notes`
column like:
    "Rolex | Submariner Date | Ref. 126610LN | Automatic Cal. 3235 | Stainless Steel"

This parser extracts that into structured fields:
    {
        "brand": "Rolex",
        "model_name": "Submariner Date",
        "reference_number": "126610LN",
        "movement": "Automatic Cal. 3235",
        "case_material": "Stainless Steel"
    }

The parser is per-category — each category has its own positional
template + regex extractors. Falls back to a generic key:value parser
when no template matches, so unknown formats degrade gracefully.

Used by:
- `migrate_notes_to_attributes.py` (one-shot DB migration)
- `import_common.CatalogItem.parse_notes_into_attributes()` (going forward)
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Regex extractors (shared)
# ---------------------------------------------------------------------------

_RE_REF = re.compile(r"^\s*(?:Ref\.?|Reference)\s*([A-Za-z0-9.\-/]+)\s*$", re.I)
_RE_SKU = re.compile(r"^\s*(?:SKU|Style|Style Code|Item)[:\s]+([A-Za-z0-9.\-/]+)\s*$", re.I)
_RE_YEAR = re.compile(r"^\s*((?:19|20)\d{2})\s*$")
_RE_CAL = re.compile(r"^\s*(?:Cal\.?|Caliber|Movement)\s*[:\s]\s*(.+?)\s*$", re.I)
_RE_AUTO_CAL = re.compile(r"^\s*(Automatic|Manual|Quartz|Solar|Spring Drive)\s*(?:Cal\.?\s*)?(.+)?$", re.I)
_RE_AGE = re.compile(r"^\s*(\d+)\s*Year(?:s)?\s*Old\s*$", re.I)
_RE_PROOF = re.compile(r"^\s*(\d{2,3}(?:\.\d+)?)\s*(?:proof|°)\s*$", re.I)
_RE_ABV = re.compile(r"^\s*(\d{2,3}(?:\.\d+)?)\s*%\s*(?:ABV|abv)?\s*$")
_RE_SIZE_ML = re.compile(r"^\s*(\d{2,4})\s*ml\s*$", re.I)
_RE_PIECE_COUNT = re.compile(r"^\s*(\d{2,5})\s+(?:pieces?|pcs?)\s*$", re.I)
_RE_SCALE = re.compile(r"^\s*1\s*[/:]\s*(\d{1,4})\s*$")


# ---------------------------------------------------------------------------
# Generic key:value extractor
# ---------------------------------------------------------------------------

def _extract_kv(part: str) -> tuple[str, Any] | None:
    """Try common key:value patterns. Returns (key, value) or None."""
    p = part.strip()
    if not p:
        return None

    # Ref. 12345 / Reference 12345
    m = _RE_REF.match(p)
    if m:
        return ("reference_number", m.group(1))

    # SKU: 555088-101 / Style Code: ABC123
    m = _RE_SKU.match(p)
    if m:
        return ("sku", m.group(1))

    # 1985 (year)
    m = _RE_YEAR.match(p)
    if m:
        return ("year", int(m.group(1)))

    # Cal. 3235 / Caliber 3235 / Movement: 7750
    m = _RE_CAL.match(p)
    if m:
        return ("movement_caliber", m.group(1).strip())

    # Automatic Cal. 3235
    m = _RE_AUTO_CAL.match(p)
    if m and m.group(2):
        return ("movement", f"{m.group(1)} {m.group(2)}".strip())

    # 12 Years Old
    m = _RE_AGE.match(p)
    if m:
        return ("age_years", int(m.group(1)))

    # 86 proof
    m = _RE_PROOF.match(p)
    if m:
        return ("proof", float(m.group(1)))

    # 43% ABV
    m = _RE_ABV.match(p)
    if m:
        return ("abv_percent", float(m.group(1)))

    # 750ml
    m = _RE_SIZE_ML.match(p)
    if m:
        return ("bottle_size_ml", int(m.group(1)))

    # 1500 pieces
    m = _RE_PIECE_COUNT.match(p)
    if m:
        return ("piece_count", int(m.group(1)))

    # 1/35, 1:48
    m = _RE_SCALE.match(p)
    if m:
        return ("scale", f"1/{m.group(1)}")

    # key: value (generic, e.g. "Color: Red")
    # Only match when key looks like a real attribute name (short, simple words)
    if ":" in p:
        k, v = p.split(":", 1)
        k_raw = k.strip()
        v = v.strip()
        # Reject if key has more than 3 words or contains non-letter chars
        if (
            k_raw and v
            and len(k_raw) <= 30
            and len(k_raw.split()) <= 3
            and re.match(r"^[A-Za-z][A-Za-z0-9 _\-/]*$", k_raw)
        ):
            k_norm = k_raw.lower().replace(" ", "_").replace("-", "_")
            return (k_norm, v)

    return None


# ---------------------------------------------------------------------------
# Per-category template parsers
# ---------------------------------------------------------------------------

def _parse_watches(parts: list[str], brand: str) -> dict[str, Any]:
    """
    Watches: 'Brand | Model Name | Ref. 12345 | Cal. 3235 | Material'
    """
    out: dict[str, Any] = {}
    if len(parts) >= 1 and parts[0].strip() and not _extract_kv(parts[0]):
        out["brand"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip() and not _extract_kv(parts[1]):
        out["model_name"] = parts[1].strip()
    if len(parts) >= 5 and parts[4].strip():
        out["case_material"] = parts[4].strip()
    return out


def _parse_sneakers(parts: list[str]) -> dict[str, Any]:
    """
    Sneakers: 'Tag | SKU: 555088-101'
    """
    out: dict[str, Any] = {}
    if parts and parts[0].strip() and ":" not in parts[0]:
        out["release_type"] = parts[0].strip()
    return out


def _parse_comic_books(parts: list[str]) -> dict[str, Any]:
    """
    Comics: 'Publisher | Title | Era Key' (e.g. 'Marvel | X-Men | Silver Age Key')
    """
    out: dict[str, Any] = {}
    if len(parts) >= 1 and parts[0].strip():
        out["publisher"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["series_title"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["key_issue_note"] = parts[2].strip()
    return out


def _parse_whiskey(parts: list[str]) -> dict[str, Any]:
    """
    Whiskey: free-form like 'Macallan | 18 Year | 750ml | 43% ABV'
    """
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["brand"] = parts[0].strip()
    return out


def _parse_lego(parts: list[str]) -> dict[str, Any]:
    """LEGO: 'Theme | Subtheme | 1500 pieces | 2020'"""
    out: dict[str, Any] = {}
    if len(parts) >= 1 and parts[0].strip():
        out["theme"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["subtheme"] = parts[1].strip()
    return out


def _parse_vinyl(parts: list[str]) -> dict[str, Any]:
    """Vinyl: 'Artist | Album | Label | Year | Format'"""
    out: dict[str, Any] = {}
    if len(parts) >= 1 and parts[0].strip():
        out["artist"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["album_title"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["label"] = parts[2].strip()
    return out


def _parse_funko(parts: list[str]) -> dict[str, Any]:
    """Funko: 'Series #Number | Exclusive Tag' (e.g. 'DC Heroes #01 | SDCC 2010')"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        # 'DC Heroes #01' → series=DC Heroes, figure_number=01
        m = re.match(r"^(.+?)\s*#(\w+)\s*$", parts[0].strip())
        if m:
            out["series"] = m.group(1).strip()
            out["figure_number"] = m.group(2)
        else:
            out["series"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["exclusive_tag"] = parts[1].strip()
    return out


def _parse_pokemon(parts: list[str]) -> dict[str, Any]:
    """Pokemon TCG: 'Set Name #Card/Total' (e.g. 'Perfect Order #1/88')"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        m = re.match(r"^(.+?)\s*#(\d+)/(\d+)\s*$", parts[0].strip())
        if m:
            out["set_name"] = m.group(1).strip()
            out["card_number"] = int(m.group(2))
            out["set_total"] = int(m.group(3))
        else:
            out["set_name"] = parts[0].strip()
    return out


def _parse_manga(parts: list[str]) -> dict[str, Any]:
    """Manga: 'X vols | Status | MAL Score'"""
    out: dict[str, Any] = {}
    for part in parts:
        p = part.strip()
        m = re.match(r"^(\d+)\s+vols?\s*$", p, re.I)
        if m:
            out["volume_count"] = int(m.group(1))
            continue
        m = re.match(r"^(Publishing|Finished|Hiatus|Cancelled)\s*$", p, re.I)
        if m:
            out["publication_status"] = m.group(1)
            continue
        m = re.match(r"^MAL\s+(\d+\.?\d*)\s*$", p, re.I)
        if m:
            out["mal_score"] = float(m.group(1))
            continue
    return out


def _parse_warhammer(parts: list[str]) -> dict[str, Any]:
    """Warhammer: 'Game System | Faction'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["game_system"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["faction"] = parts[1].strip()
    return out


def _parse_disney(parts: list[str]) -> dict[str, Any]:
    """Disney: 'Product Type | LE Edition' (e.g. 'pins | LE 2500')"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["product_type"] = parts[0].strip()
    for part in parts[1:]:
        p = part.strip()
        m = re.match(r"^LE\s+(\d+)\s*$", p, re.I)
        if m:
            out["limited_edition_size"] = int(m.group(1))
    return out


def _parse_loungefly(parts: list[str]) -> dict[str, Any]:
    """Loungefly: 'Franchise | Product Type | Retailer'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["franchise"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["product_type"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["retailer"] = parts[2].strip()
    return out


def _parse_ghibli(parts: list[str]) -> dict[str, Any]:
    """Studio Ghibli: 'Film | Product Type'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["film_title"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["product_type"] = parts[1].strip()
    return out


def _parse_kpop(parts: list[str]) -> dict[str, Any]:
    """K-pop merch: 'Group | Album/Era | Variant'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["group_name"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["album_era"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["variant"] = parts[2].strip()
    return out


def _parse_lorcana(parts: list[str]) -> dict[str, Any]:
    """Lorcana: 'Set Name | Ink Color | Rarity'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["set_name"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["ink_color"] = parts[1].strip()
    return out


def _parse_keycaps(parts: list[str]) -> dict[str, Any]:
    """Keycaps: 'Profile | Material | Mount'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["profile"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["material"] = parts[1].strip()
    return out


def _parse_sportscards(parts: list[str]) -> dict[str, Any]:
    """Sports cards: 'Year Brand Set | Player | Parallel'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["set_info"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["player_name"] = parts[1].strip()
    return out


def _parse_retro_games(parts: list[str]) -> dict[str, Any]:
    """Retro games: 'Platform | Region | CIB Status'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["platform"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["region"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["cib_status"] = parts[2].strip()
    return out


def _parse_vintage_toys(parts: list[str]) -> dict[str, Any]:
    """Vintage toys: 'Manufacturer | Year | Condition'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["manufacturer"] = parts[0].strip()
    return out


def _parse_oop_board_games(parts: list[str]) -> dict[str, Any]:
    """OOP board games: 'Publisher | Designer | Edition'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["publisher"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["designer"] = parts[1].strip()
    return out


def _parse_anime_bluray(parts: list[str]) -> dict[str, Any]:
    """Anime Blu-ray: 'Publisher | Edition | Format'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["publisher"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["edition"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["format"] = parts[2].strip()
    return out


def _parse_bluray_steelbook(parts: list[str]) -> dict[str, Any]:
    """Blu-ray steelbook: 'Distributor | Spine Number | Format'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["distributor"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["edition"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["format"] = parts[2].strip()
    return out


def _parse_designer_toys(parts: list[str]) -> dict[str, Any]:
    """Designer toys: 'Artist | Series | Edition'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["artist"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["series"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["edition"] = parts[2].strip()
    return out


def _parse_manufacturer_line_franchise(parts: list[str]) -> dict[str, Any]:
    """Generic 'Manufacturer | Product Line | Franchise | Detail' parser."""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["manufacturer"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["product_line"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["franchise"] = parts[2].strip()
    if len(parts) >= 4 and parts[3].strip():
        out["detail"] = parts[3].strip()
    return out


def _parse_anime_soundtrack(parts: list[str]) -> dict[str, Any]:
    """Anime OST: 'Anime | Composer | Format | Edition'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["anime_franchise"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["composer"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["format"] = parts[2].strip()
    if len(parts) >= 4 and parts[3].strip():
        out["edition"] = parts[3].strip()
    return out


def _parse_gunpla(parts: list[str]) -> dict[str, Any]:
    """Gunpla: 'Grade Scale | Series'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        # Extract grade and scale: "PG 1/60"
        m = re.match(r"^(PG|MG|RG|HG|HGUC|SD|FM|RE/100|EG)\s*(?:1\s*[/:]?\s*(\d+))?", parts[0].strip(), re.I)
        if m:
            out["grade"] = m.group(1)
            if m.group(2):
                out["scale"] = f"1/{m.group(2)}"
        else:
            out["grade_scale"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["series"] = parts[1].strip()
    return out


def _parse_franchise_type(parts: list[str]) -> dict[str, Any]:
    """Generic 'Franchise | Type | [Variant]' parser used by many fandom categories."""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["franchise"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["product_type"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["variant"] = parts[2].strip()
    return out


def _parse_vtuber(parts: list[str]) -> dict[str, Any]:
    """VTuber: 'Agency | Talent | Product Type | Event'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["agency"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["talent_name"] = parts[1].strip()
    if len(parts) >= 3 and parts[2].strip():
        out["product_type"] = parts[2].strip()
    if len(parts) >= 4 and parts[3].strip():
        out["event"] = parts[3].strip()
    return out


def _parse_plush(parts: list[str]) -> dict[str, Any]:
    """Plush: 'Brand | Squad/Line | Description'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["brand"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["squad"] = parts[1].strip()
    return out


def _parse_blind_box(parts: list[str]) -> dict[str, Any]:
    """Blind box: free-text description, extract series count"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        m = re.search(r"(\d+)\s+designs", parts[0], re.I)
        if m:
            out["series_count"] = int(m.group(1))
        out["description"] = parts[0].strip()
    return out


def _parse_fragrances(parts: list[str]) -> dict[str, Any]:
    """Fragrances: 'House | Scent Family | Concentration'"""
    out: dict[str, Any] = {}
    if parts and parts[0].strip():
        out["house"] = parts[0].strip()
    if len(parts) >= 2 and parts[1].strip():
        out["family"] = parts[1].strip()
    return out


# ---------------------------------------------------------------------------
# Category dispatch
# ---------------------------------------------------------------------------

_CATEGORY_PARSERS = {
    "watches": _parse_watches,
    "sneakers": lambda parts, brand: _parse_sneakers(parts),
    "comic_books": lambda parts, brand: _parse_comic_books(parts),
    "whiskey": lambda parts, brand: _parse_whiskey(parts),
    "lego": lambda parts, brand: _parse_lego(parts),
    "vinyl_records": lambda parts, brand: _parse_vinyl(parts),
    "city_pop_vinyl": lambda parts, brand: _parse_vinyl(parts),
    "anime_ost_vinyl": lambda parts, brand: _parse_vinyl(parts),
    "funko": lambda parts, brand: _parse_funko(parts),
    "pokemon": lambda parts, brand: _parse_pokemon(parts),
    "manga": lambda parts, brand: _parse_manga(parts),
    "warhammer": lambda parts, brand: _parse_warhammer(parts),
    "disney": lambda parts, brand: _parse_disney(parts),
    "loungefly": lambda parts, brand: _parse_loungefly(parts),
    "ghibli": lambda parts, brand: _parse_ghibli(parts),
    "kpop_merch": lambda parts, brand: _parse_kpop(parts),
    "kpop_lightsticks": lambda parts, brand: _parse_kpop(parts),
    "lorcana": lambda parts, brand: _parse_lorcana(parts),
    "keycaps": lambda parts, brand: _parse_keycaps(parts),
    "sportscards": lambda parts, brand: _parse_sportscards(parts),
    "retro_games": lambda parts, brand: _parse_retro_games(parts),
    "retro_handhelds": lambda parts, brand: _parse_retro_games(parts),
    "vintage_toys": lambda parts, brand: _parse_vintage_toys(parts),
    "vintage_cameras": lambda parts, brand: _parse_vintage_toys(parts),
    "oop_board_games": lambda parts, brand: _parse_oop_board_games(parts),
    "fragrances": lambda parts, brand: _parse_fragrances(parts),
    "anime_bluray": lambda parts, brand: _parse_anime_bluray(parts),
    "bluray_steelbook": lambda parts, brand: _parse_bluray_steelbook(parts),
    "designer_toys": lambda parts, brand: _parse_designer_toys(parts),
    "blind_box": lambda parts, brand: _parse_blind_box(parts),
    "nintendo_merch": lambda parts, brand: _parse_franchise_type(parts),
    "one_piece": lambda parts, brand: _parse_franchise_type(parts),
    "pop_fandom": lambda parts, brand: _parse_franchise_type(parts),
    "retro_pokemon": lambda parts, brand: _parse_franchise_type(parts),
    "theme_park": lambda parts, brand: _parse_franchise_type(parts),
    "vtuber": lambda parts, brand: _parse_vtuber(parts),
    "plush_collectibles": lambda parts, brand: _parse_plush(parts),
    "action_figures": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "anime_figures": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "bandai_premium": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "marvel_legends": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "hot_toys": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "anime_soundtrack": lambda parts, brand: _parse_anime_soundtrack(parts),
    "gunpla": lambda parts, brand: _parse_gunpla(parts),
    "scale_models": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "jp_event": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    "jp_magazine": lambda parts, brand: _parse_manufacturer_line_franchise(parts),
    # TCGs share the pokemon-style format
    "yugioh": lambda parts, brand: _parse_pokemon(parts),
    "mtg": lambda parts, brand: _parse_pokemon(parts),
    "digimon": lambda parts, brand: _parse_pokemon(parts),
    "one_piece_tcg": lambda parts, brand: _parse_pokemon(parts),
}


def parse_notes(category: str, notes: str, brand: str = "") -> dict[str, Any]:
    """
    Parse a free-text notes field into structured attributes.

    Strategy:
      1. Split on '|' separator
      2. Try category-specific positional parser if available
      3. Run generic key:value extractor on every part
      4. Merge: category-specific wins for known fields, generic adds the rest

    Returns an empty dict if notes is empty or unparseable.
    """
    if not notes or not notes.strip():
        return {}

    parts = [p.strip() for p in notes.split("|")]

    out: dict[str, Any] = {}

    # Category-specific positional parsing
    parser = _CATEGORY_PARSERS.get(category)
    if parser:
        try:
            out.update(parser(parts, brand))
        except Exception:
            pass  # fall through to generic

    # Generic key:value extraction — only run for unknown categories,
    # OR for parts that contain explicit "key: value" patterns or
    # well-known regex matches (Ref., SKU, year, etc.)
    if not parser:
        for part in parts:
            kv = _extract_kv(part)
            if kv:
                key, value = kv
                if key not in out:
                    out[key] = value
    else:
        # For known categories, only extract well-defined patterns from
        # parts the category parser didn't already consume
        for part in parts:
            kv = _extract_kv(part)
            if kv:
                key, value = kv
                # Only accept patterns from named regex (not generic kv)
                if key in {
                    "reference_number", "sku", "year", "movement_caliber",
                    "movement", "age_years", "proof", "abv_percent",
                    "bottle_size_ml", "piece_count", "scale",
                } and key not in out:
                    out[key] = value

    return out


# ---------------------------------------------------------------------------
# Migration helper
# ---------------------------------------------------------------------------

def parse_into_catalog_item(item: Any) -> int:
    """
    Mutate a CatalogItem in place: parse `notes` into `attributes_json`.
    Returns the number of attributes added.

    Existing attributes_json keys are preserved (notes-derived values
    only fill in missing keys).
    """
    if not getattr(item, "notes", "") or not item.notes.strip():
        return 0

    parsed = parse_notes(item.category, item.notes, getattr(item, "brand", ""))
    if not parsed:
        return 0

    if not hasattr(item, "attributes_json") or item.attributes_json is None:
        item.attributes_json = {}

    added = 0
    for k, v in parsed.items():
        if k not in item.attributes_json:
            item.attributes_json[k] = v
            added += 1

    return added
