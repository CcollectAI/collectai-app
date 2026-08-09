#!/usr/bin/env python3
"""
Probe that the add paths actually RESOLVE a canonical_key, not just that the
column appears in their INSERT.

audit_item_writers.py asks a STRUCTURAL question: is canonical_key in the
column list? That passes even if _resolve_canonical_key returns None for every
real input — in which case the fix is inert and every item is still unpriceable,
with a green check to prove it. This is the exact trap CLAUDE.md records
("Structural checks cannot catch this class"): the table existed, the columns
matched, the SQL was valid, the endpoint returned 200, and the join still
matched nothing for four months.

So this asks about VALUES: feed the resolver titles that are literally IN the
catalog and confirm it returns their key. If a title taken verbatim from
category_items does not resolve, nothing a user types ever will.

Sampling is STRATIFIED by category. An unordered LIMIT returns one contiguous
physical run, which flatters or damns a single category by accident — that
sampling bias has bitten this project four times.

Usage:
    python3 server/scripts/probe_canonical_key_resolution.py
    python3 server/scripts/probe_canonical_key_resolution.py --json
Requires DB_DSN_DIRECT. Read-only: creates no rows.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# The bake runs with WorkingDirectory=/opt/collectors/server so `app.*` resolves;
# a script invoked directly from scripts/ does not inherit that. Add the server
# root explicitly rather than depending on how the script happens to be called.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg not installed — run on EC2 (/opt/collectors/.venv)", file=sys.stderr)
    raise SystemExit(2)

PER_CATEGORY = 5
# Categories worth probing: the ones a user can actually add and price. Pulled
# from the live catalog rather than hardcoded, so a new category is covered
# automatically.
CATEGORY_SQL = """
    SELECT category, count(*) AS n
    FROM category_items
    WHERE item_key IS NOT NULL AND title IS NOT NULL
    GROUP BY category
    HAVING count(*) >= 50
    ORDER BY n DESC
    LIMIT 8
"""

SAMPLE_SQL = """
    SELECT title, item_key
    FROM category_items
    WHERE category = $1 AND item_key IS NOT NULL AND title IS NOT NULL
    ORDER BY md5(item_key)     -- deterministic but not physical order
    LIMIT $2
"""


async def main() -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    # The resolver needs a pool, not a bare connection.
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        from app.agents.intake.catalog_matching import _match_catalog_items

        cats = await pool.fetch(CATEGORY_SQL)
        results = []
        for c in cats:
            rows = await pool.fetch(SAMPLE_SQL, c["category"], PER_CATEGORY)
            for r in rows:
                matched_key = None
                try:
                    matches = await _match_catalog_items(
                        category_id=c["category"],
                        suggested_name=r["title"],
                        search_keywords=[],
                        brand=None,
                        set_code=None,
                        pool=pool,
                        extracted_attributes=None,
                    )
                    if matches and float(matches[0].get("match_score") or 0) >= 0.75:
                        matched_key = matches[0].get("item_key")
                except Exception as e:  # noqa: BLE001 - probe reports, never raises
                    matched_key = f"ERROR: {e}"
                results.append({
                    "category": c["category"],
                    "title": r["title"],
                    "expected_key": r["item_key"],
                    "resolved_key": matched_key,
                    "exact": matched_key == r["item_key"],
                    "any": bool(matched_key) and not str(matched_key).startswith("ERROR"),
                })
    finally:
        await pool.close()

    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2, default=str))
    else:
        print("\n=== canonical_key resolution probe (values, not structure) ===\n")
        print("  Titles taken VERBATIM from the catalog. If these do not resolve,")
        print("  nothing a user types will, and every added item stays unpriceable.\n")
        print(f"  {'category':16} {'exact':>7} {'any':>6} {'n':>4}")
        for cat, rs in by_cat.items():
            ex = sum(1 for r in rs if r["exact"])
            an = sum(1 for r in rs if r["any"])
            print(f"  {cat:16} {ex:>7} {an:>6} {len(rs):>4}")
        total = len(results)
        exact = sum(1 for r in results if r["exact"])
        anyk = sum(1 for r in results if r["any"])
        print(f"\n  overall: {exact}/{total} exact key, {anyk}/{total} resolved anything")
        dead = [c for c, rs in by_cat.items() if not any(r["any"] for r in rs)]
        for c in dead:
            print(f"    DEAD  {c}: not one catalog title resolved — adds here stay unpriceable")
        print()

    # Fail if a whole category resolves nothing: that is a real dead path.
    dead = [c for c, rs in by_cat.items() if not any(r["any"] for r in rs)]
    return 1 if dead else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
