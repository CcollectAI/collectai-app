"""Set completion derives the set from the catalogue card (2026-09-26).

It read only items.attrs->>'set_name', which almost no item carries (2 of 10
catalogue-linked items on prod), so "Finish a set" was empty for nearly every
member. Pins the query shape: catalogue fallback, distinct cards.
"""
import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "app/features/set_router.py").read_text()


def _auto_sql():
    blocks = [m.group(1) for m in re.finditer(r'f"""(.*?)"""', SRC, re.S) if "catalog_totals" in m.group(1)]
    assert blocks, "auto-progress query not found"
    return re.sub(r"--[^\n]*", "", blocks[0])


def test_set_name_falls_back_to_the_catalogue_card():
    q = _auto_sql()
    assert re.search(r"LEFT JOIN\s+category_items\s+ci\s+ON\s+ci\.category\s*=\s*items\.category\s+AND\s+ci\.item_key\s*=\s*items\.canonical_key", q)
    assert re.search(r"COALESCE\(\s*NULLIF\(items\.attrs\s*->>\s*'set_name'", q)
    assert "ci.attributes_json ->> 'set_name'" in q


def test_counts_distinct_cards_and_skips_archived():
    q = _auto_sql()
    assert "COUNT(DISTINCT card)" in q
    assert re.search(r"NOT\s+items\.archived", q)
