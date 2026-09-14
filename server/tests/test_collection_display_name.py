"""The "Browse by Set" rail must print a set's NAME, not its code.

WHY (2026-09-14): walked on Android, Pokémon's category page offered tiles
reading "Swsh8" and "Smp" (Fusion Strike, SM Black Star Promos). The only label
source was `_humanize_set_code`, which capitalises a code; the real name was in
`category_items.attributes_json->>'set'` all along. `mv_catalog_collections` now
carries it as `set_name` — filled only when unique within the category, because
sportscards reuses "Panini Prizm" for every year
(server/scripts/20260914_collection_set_names.sql).

The humaniser also damaged codes that were already readable: `capitalize()`
lowercases the rest of each word, so "CBS/Sony" printed "Cbs/sony".
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-for-unit-tests-only-32ch")

from app.features.catalog_browser_router import (  # noqa: E402
    _collection_display_name,
    _humanize_set_code,
)


def test_set_name_wins_over_the_code():
    assert _collection_display_name("swsh8", "Fusion Strike", "set") == "Fusion Strike"
    assert _collection_display_name("smp", "SM Black Star Promos", "set") == "SM Black Star Promos"


def test_no_set_name_falls_back_to_the_humanised_code():
    # The MV leaves set_name NULL when the name is shared across codes — the code
    # is then the only thing that carries the year.
    assert _collection_display_name("2023-panini-prizm", None, "set") == "2023 Panini Prizm"
    assert _collection_display_name("gundam-wing", None, "set") == "Gundam Wing"


def test_brand_is_printed_as_stored():
    assert _collection_display_name("Omega", None, "brand") == "Omega"
    # A brand row never carries a set_name; even if one leaked in, brand wins.
    assert _collection_display_name("Omega", "Something", "brand") == "Omega"


def test_humanise_rewrites_lowercase_slugs_only():
    assert _humanize_set_code("base-set-2") == "Base Set 2"
    assert _humanize_set_code("hot_toys") == "Hot Toys"
    # Already display-form codes, measured on prod 2026-09-14 — capitalize()
    # used to lowercase the tail of each word.
    for code in ("CBS/Sony", "SB Dunk Low", "OP-PR", "BT01-03A", "EDP", "37.09 Bluefin"):
        assert _humanize_set_code(code) == code
    # No letters at all (a LEGO set number): "10274 1" would be worse than the code.
    assert _humanize_set_code("10274-1") == "10274-1"
    # Lowercase codes with punctuation are still humanised, not returned raw —
    # the first guard (a [a-z0-9_-] slug regex) printed "ad&d-2e" here.
    assert _humanize_set_code("ad&d-2e") == "Ad&d 2e"
    assert _humanize_set_code("drawn-&-quarterly") == "Drawn & Quarterly"


def test_empty_set_name_is_not_a_name():
    # NULLIF in the MV should make this impossible; the fallback must still hold.
    assert _collection_display_name("swsh8", "", "set") == "Swsh8"
