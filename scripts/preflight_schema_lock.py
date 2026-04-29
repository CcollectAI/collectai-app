#!/usr/bin/env python3
"""Preflight gate: live DB schema must be a superset of schema.lock.json.

The lock file is the frozen contract between code and DB. If the live
DB has DROPPED or RENAMED a column the lock declares, the gate fails
loudly — which would have caught the items.attributes_json → items.attrs
rename on the day it landed instead of weeks later.

Adding new columns to the live DB is fine and silent (the lock isn't
violated); regenerate the lock when those columns become required by
new code via `python3 scripts/regen_schema_lock.py`.

Exit codes:
  0 — lock satisfied (live ⊇ lock)
  1 — drift: a locked table or column is missing live
  2 — DB unreachable, lock file missing, or other config error
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

LOCK = Path(__file__).resolve().parent / "schema.lock.json"


async def fetch_live() -> dict[str, set[str]]:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr)
        sys.exit(2)
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='public'"
        )
    finally:
        await conn.close()
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(r["table_name"], set()).add(r["column_name"])
    return out


def main() -> None:
    if not LOCK.exists():
        print(f"ERROR: lock file not found at {LOCK}", file=sys.stderr)
        sys.exit(2)
    payload = json.loads(LOCK.read_text())
    locked = {k: set(v) for k, v in payload["tables"].items()}
    live = asyncio.run(fetch_live())

    missing_tables: list[str] = []
    missing_columns: list[tuple[str, str]] = []
    for table, cols in locked.items():
        if table not in live:
            missing_tables.append(table)
            continue
        for col in cols:
            if col not in live[table]:
                missing_columns.append((table, col))

    print("─" * 72)
    print(f"  Schema lock check — {len(locked)} tables")
    print("─" * 72)

    if not missing_tables and not missing_columns:
        print(f"✅ Live schema satisfies the lock ({len(locked)} tables, all columns present).")
        print("─" * 72)
        print("  verdict: PASS")
        print("─" * 72)
        sys.exit(0)

    if missing_tables:
        print(f"\n❌ {len(missing_tables)} locked tables MISSING from live DB:")
        for t in sorted(missing_tables):
            print(f"  - {t}")
    if missing_columns:
        print(f"\n❌ {len(missing_columns)} locked columns MISSING from live DB:")
        for t, c in sorted(missing_columns):
            print(f"  - {t}.{c}")
    print()
    print("If the change is intentional, update code to stop using the dropped")
    print("name AND regenerate the lock: `python3 scripts/regen_schema_lock.py`.")
    print("─" * 72)
    print("  verdict: FAIL")
    print("─" * 72)
    sys.exit(1)


if __name__ == "__main__":
    main()
