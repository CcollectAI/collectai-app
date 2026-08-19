"""Static gate: every `alias.column` in an inline SQL string must exist.

WHY THIS EXISTS (incident, 2026-08-15)
--------------------------------------
`p2p_offers_router.py` selected `l.image_url AS listing_image_url`, where `l`
is `marketplace_listings`. That column has never existed on that table and no
migration ever added it. The code was committed, reviewed, and sat in `main`
for hours looking fine — because the router had not been DEPLOYED, so the query
was never executed. The moment it was deployed, every `GET /p2p/offers` call
returned 500 `UndefinedColumnError`, taking the Open bids screen down.

Nothing could have caught it earlier:
  - `tsc` and `jest` do not read Python.
  - The router's own 30 tests inspect SQL as TEXT, so they happily matched a
    column name that does not exist.
  - `preflight_schema_lock.py` compares the LIVE DB against the lock; it knows
    nothing about what the code asks for.

So the missing check is the third side of that triangle: what the CODE asks for
versus what the schema HAS. That is this file.

WHAT IT DOES
------------
For every triple-quoted SQL string in server/app/**/*.py:
  1. Build an alias -> table map from `FROM|JOIN [public.]<table> [AS] <alias>`.
  2. Collect every `<alias>.<column>` reference.
  3. Resolve each against scripts/schema.lock.json and report the misses.

Deliberately conservative — it reports ONLY references whose alias resolves to
a table the lock knows. An unresolvable alias (CTE, subquery, function call) is
skipped rather than guessed at, because a checker that cries wolf gets muted,
and a muted checker is worse than no checker at all.

Usage:  python3 server/scripts/check_sql_columns.py [--verbose]
Exit 1 on any unknown column.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "server" / "app"
LOCK = ROOT / "scripts" / "schema.lock.json"

# `FROM public.items i` / `JOIN marketplace_listings AS l` / `FROM items`
_FROM_JOIN = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-z_][a-z0-9_]*)\s+(?:AS\s+)?([a-z_][a-z0-9_]*)\b",
    re.I,
)
# `l.image_url`, but not `1.5`, not `o.` at end of a word boundary
_REF = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b")
_SQL_BLOCK = re.compile(r'"""(.*?)"""', re.S)

# Aliases/keywords that are never table aliases in these queries.
_NOT_ALIASES = {
    "self", "os", "json", "re", "sys", "logger", "np", "pd", "datetime", "uuid",
    "asyncio", "math", "time", "e", "exc", "err", "conn", "pool", "payload",
    "settings", "request", "response", "row", "r", "app", "router", "Path",
}
# SQL keywords that can follow FROM/JOIN and are not tables.
_NOT_TABLES = {"lateral", "unnest", "generate_series", "jsonb_array_elements", "select"}


def load_schema() -> dict[str, set[str]]:
    lock = json.loads(LOCK.read_text())
    tables = lock.get("tables", {})
    out: dict[str, set[str]] = {}
    for table, cols in tables.items():
        if isinstance(cols, dict):
            out[table] = set(cols.keys())
        elif isinstance(cols, list):
            out[table] = {c if isinstance(c, str) else c.get("name", "") for c in cols}
    return out


def check_file(path: Path, schema: dict[str, set[str]], verbose: bool) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="ignore")
    problems: list[str] = []

    # ALIASES ARE RESOLVED PER FILE, NOT PER SQL STRING.
    #
    # The first version of this checker scoped aliases to the block they
    # appeared in and reported a clean bill of health on the very bug it was
    # written for. The reason is worth keeping: `_OFFER_COLUMNS` is a bare
    # column list in its own triple-quoted string — no FROM, no JOIN — that
    # five other queries interpolate. Inside that block `l` resolves to
    # nothing, so `l.image_url` was skipped as unresolvable rather than
    # flagged as wrong. A gate whose axis is the wrong scope reports success
    # forever (learning_sql_in_a_python_string_is_invisible_to_js_checkers).
    #
    # An alias bound to two different tables anywhere in the file is dropped
    # rather than guessed at — better silent on the ambiguous case than noisy.
    alias_tables: dict[str, set[str]] = {}
    for table, alias in _FROM_JOIN.findall(re.sub(r"--[^\n]*", "", src)):
        if table.lower() in _NOT_TABLES:
            continue
        alias_tables.setdefault(alias.lower(), set()).add(table.lower())
    aliases = {a: next(iter(t)) for a, t in alias_tables.items() if len(t) == 1}
    if verbose and alias_tables:
        ambiguous = {a: t for a, t in alias_tables.items() if len(t) > 1}
        if ambiguous:
            print(f"  {path.name}: ambiguous aliases skipped: {ambiguous}")

    # EVERY triple-quoted block, with no "does this look like SQL?" filter.
    #
    # Second false-green, same root cause as the alias scoping above: the
    # filter was `block must contain SELECT|INSERT|UPDATE|DELETE`, and
    # `_OFFER_COLUMNS` is a bare comma-separated column list with none of those
    # words in it. The one block holding the bug was the one block skipped.
    #
    # Dropping the filter means docstrings are scanned too. That is harmless
    # here: a reference is only ever checked when its alias was bound by a
    # FROM/JOIN somewhere in the same file, so prose about `docs/foo.md` or
    # `p2p_offers.status` resolves to nothing and is ignored.
    for block in _SQL_BLOCK.findall(src):
        # Strip SQL comments — they name columns in prose constantly.
        sql = re.sub(r"--[^\n]*", "", block)

        for alias, col in set(_REF.findall(sql)):
            a = alias.lower()
            if a in _NOT_ALIASES or a not in aliases:
                continue
            table = aliases[a]
            cols = schema.get(table)
            if cols is None:
                if verbose:
                    print(f"  skip (table not in lock): {table}")
                continue
            if col.lower() not in {c.lower() for c in cols}:
                line = next(
                    (i + 1 for i, ln in enumerate(src.splitlines())
                     if f"{alias}.{col}" in ln),
                    0,
                )
                problems.append(
                    f"{path.relative_to(ROOT)}:{line}: "
                    f"{alias}.{col} — {table} has no column '{col}'"
                )
    return problems


def main() -> int:
    verbose = "--verbose" in sys.argv
    if not LOCK.exists():
        print(f"FATAL: {LOCK} missing — run scripts/regen_schema_lock.py")
        return 2
    schema = load_schema()

    problems: list[str] = []
    files = sorted(APP.rglob("*.py"))
    for f in files:
        problems.extend(check_file(f, schema, verbose))

    print("─" * 72)
    print(f"  SQL column check — {len(files)} files, {len(schema)} tables in lock")
    print("─" * 72)
    if problems:
        print(f"\n❌ {len(problems)} SQL reference(s) to columns that do not exist:\n")
        for p in problems:
            print(f"  - {p}")
        print("\nA query like this is undeployable: it passes every test that reads")
        print("SQL as text, and 500s the first time it is actually executed.")
        print("─" * 72)
        return 1
    print("\n✅ every resolvable alias.column exists in the schema lock")
    print("─" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
