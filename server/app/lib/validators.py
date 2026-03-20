"""
Shared input validators for query parameters and request bodies.

Centralises category allowlists and format checks so every router
uses the same rules.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Category allowlist
# ---------------------------------------------------------------------------
# Canonical list of all valid category IDs.  Kept as a frozenset for O(1)
# membership checks.  When adding a new category, update BOTH this set AND
# ``app/ml/vision_classifier.ALL_CATEGORIES``.

VALID_CATEGORY_IDS: frozenset[str] = frozenset({
    # TCGs
    "pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg",
    # Toys / Figures
    "funko", "designer_toys", "anime_figures", "hot_toys",
    "action_figures", "vintage_toys", "marvel_legends",
    # Building / Models
    "lego", "gunpla", "scale_models", "warhammer",
    # Gaming
    "retro_games",
    # Media
    "manga", "comic_books", "bluray_steelbook", "anime_bluray", "anime_soundtrack",
    "anime_ost_vinyl",
    # Music / Fandom
    "kpop_merch", "taylor_swift", "pop_fandom", "kpop_lightsticks",
    "vinyl_records",
    # Disney / Theme Parks
    "disney", "theme_park", "ghibli",
    # Japan Exclusives
    "bandai_premium", "jp_magazine", "jp_event",
    # Nintendo / Pokemon Merch
    "nintendo_merch", "retro_pokemon",
    # IP-Specific
    "one_piece", "vtuber",
    # Niche
    "keycaps", "loungefly",
    # Lifestyle
    "sneakers", "watches",
    # Collectibles
    "blind_box", "plush_collectibles",
    # Spirits / Luxury
    "whiskey", "vintage_cameras", "pens",
    # Legacy
    "diecast", "sportscards", "retro_handhelds",
    # New Categories
    "oop_board_games", "city_pop_vinyl", "fragrances",
})


def is_valid_category(category: str | None) -> bool:
    """Return True if *category* is None (optional) or a known category ID."""
    if category is None:
        return True
    return category in VALID_CATEGORY_IDS


# ---------------------------------------------------------------------------
# Barcode format validation
# ---------------------------------------------------------------------------
# Accepts UPC-A (12 digits), EAN-13 (13), ISBN-10 (9 digits + check),
# ISBN-13, and extended barcodes up to 50 chars of alphanumeric + hyphens.

_BARCODE_RE = re.compile(r"^[A-Za-z0-9\-]{1,50}$")


def is_valid_barcode(barcode: str) -> bool:
    """Return True if *barcode* matches the expected format."""
    return bool(_BARCODE_RE.match(barcode))
