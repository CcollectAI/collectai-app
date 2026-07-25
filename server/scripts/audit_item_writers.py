#!/usr/bin/env python3
"""
Audit every INSERT INTO items for canonical_key coverage.

An item without canonical_key can never be priced. The chain is:

    canonical_key  --trg_items_canonical_ref-->  canonical_ref
                   --join-->  price_predictions.item_ref  -->  a price

Miss the first link and the item shows "—" forever. Nothing errors, nothing
logs; the item saves fine and simply never gets a value. Indistinguishable from
"we have no price for this yet".

2026-07-25: canonical_key was wired into QuickScan and add-manual, and the sweep
stopped there. /intake/save (barcode + ISBN scan) and import_router (Excel/CSV
bulk upload) both INSERT INTO items without it, so every item added through
either path was permanently unpriceable. 6 of 8 items in the live DB had no
canonical_key.

This is the recurring shape: a fix applied to SOME call sites of a pattern, and
the rest never swept. Grep the PATTERN, not the file.

Usage:
    python3 server/scripts/audit_item_writers.py          # exit 1 on gaps
    python3 server/scripts/audit_item_writers.py --json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]

# Writers that legitimately do not set canonical_key, each with the reason.
# An entry here is a decision; a missing writer is a bug.
EXEMPT: dict[str, str] = {
    "server/pipelines/seed_beta_users.py": (
        "Seeds demo accounts. Its rows are disposable fixtures, never a real "
        "user's collection, so an unpriceable item there costs nothing."
    ),
}

# Test and e2e fixtures write items to exercise unrelated code paths; requiring
# canonical_key there would only add noise to a check whose whole value is that
# a hit means a real user's item cannot be priced.
SKIP_DIRS = ("server/tests/",)

INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?items\s*\((?P<cols>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)


def find_writers() -> list[dict]:
    out: list[dict] = []
    for path in SERVER.rglob("*.py"):
        if "__pycache__" in str(path) or ".venv" in str(path):
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in INSERT_RE.finditer(src):
            cols = {c.strip().strip('"') for c in m.group("cols").split(",")}
            rel = str(path.relative_to(SERVER.parent))
            if rel.startswith(SKIP_DIRS):
                continue
            out.append({
                "file": rel,
                "line": src[: m.start()].count("\n") + 1,
                "has_canonical_key": "canonical_key" in cols or "canonical_ref" in cols,
                "columns": sorted(c for c in cols if c),
            })
    return out


def main() -> int:
    writers = find_writers()
    gaps = [w for w in writers if not w["has_canonical_key"] and w["file"] not in EXEMPT]
    stale = sorted(set(EXEMPT) - {w["file"] for w in writers})

    if "--json" in sys.argv:
        print(json.dumps({"writers": len(writers), "gaps": gaps, "stale_exempt": stale}, indent=2))
    else:
        print("\n=== INSERT INTO items — canonical_key coverage ===\n")
        print(f"  writers found            : {len(writers)}")
        print(f"  writing canonical_key    : {len(writers) - len(gaps) - len(EXEMPT)}")
        print(f"  documented exemptions    : {len(EXEMPT)}")
        print(f"  MISSING canonical_key    : {len(gaps)}\n")
        for w in gaps:
            print(f"    GAP  {w['file']}:{w['line']}")
            print(f"         items written here can NEVER be priced (no canonical_key)")
        for f in stale:
            print(f"    STALE  {f} is exempt but no longer writes items")
        if not gaps and not stale:
            print("    clean — every items writer supplies canonical_key\n")
        print()

    return 1 if (gaps or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
