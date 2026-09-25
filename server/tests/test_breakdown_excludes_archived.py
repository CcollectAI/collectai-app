"""Portfolio breakdown and exposure must not count archived items (2026-09-25).

The breakdown's `NOT i.archived` (69cbdc6e) was lost in a later rewrite while
its comment kept claiming it: Home showed Collection Value €1.313 beside a
"Portfolio" stat of €1.348, the gap being an archived card. Reads the source,
so a future rewrite that drops the filter fails here.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _sql_blocks(path):
    src = (ROOT / path).read_text()
    # SQL comments stripped: the breakdown's own comment says "`NOT i.archived`
    # was added…", which satisfied the first version of this test with the
    # filter deleted.
    return [re.sub(r"--[^\n]*", "", m.group(2)) for m in re.finditer(r'("""|\'\'\')(.*?)\1', src, re.S)]


def _items_aggregate_blocks(path):
    return [q for q in _sql_blocks(path)
            if re.search(r"\bFROM\s+items\b", q) and re.search(r"user_id\s*=\s*\$1", q)
            and re.search(r"\b(SUM|COUNT)\s*\(", q)]


def test_category_breakdown_filters_archived():
    blocks = _items_aggregate_blocks("app/features/trends_and_deepdive_router.py")
    target = [q for q in blocks if "item_value_v1" in q]
    assert target, "category-breakdown query not found"
    for q in target:
        assert re.search(r"NOT\s+i\.archived", q), "breakdown counts archived items"


def test_category_exposure_filters_archived():
    blocks = _items_aggregate_blocks("app/features/insights_router.py")
    assert blocks, "exposure query not found"
    for q in blocks:
        assert re.search(r"NOT\s+archived", q), "exposure counts archived items"
