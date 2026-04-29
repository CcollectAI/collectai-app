#!/usr/bin/env python3
"""Preflight gate: live DB schema must be a superset of schema.lock.json.

The lock is the frozen contract between code and DB. Each of the
following diff types makes the gate fail:

  - locked TABLE missing from live
  - locked COLUMN missing from live
  - locked column TYPE changed (e.g. numeric → text)
  - locked NOT NULL flipped to NULL (a downstream INSERT may now
    persist garbage; readers may now hit unexpected nulls)
  - locked column flipped from NULL → NOT NULL (every existing INSERT
    that omits the column now 500's silently)
  - locked UNIQUE key removed (UPSERT/ON CONFLICT silently no-ops)
  - locked CHECK constraint removed (FE inserts that previously
    400'd on invalid values now silently persist them)

Adding new tables/columns/constraints to live is fine and silent.
Regenerate the lock when the change is intentional via:
  python3 scripts/regen_schema_lock.py

Exit codes:
  0 — lock satisfied (live ⊇ lock)
  1 — drift
  2 — DB unreachable, lock missing, or other config error
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

LOCK = Path(__file__).resolve().parent / "schema.lock.json"


async def fetch_live() -> dict:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr)
        sys.exit(2)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET statement_timeout = 0")
        col_rows = await conn.fetch(
            """
            SELECT table_name, column_name, udt_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public'
            """
        )
        unique_rows = await conn.fetch(
            """
            SELECT t.relname AS tbl,
                   array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS cols
            FROM pg_class t
            JOIN pg_namespace n ON t.relnamespace = n.oid
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE n.nspname='public' AND ix.indisunique
            GROUP BY t.relname, i.relname
            """
        )
        check_rows = await conn.fetch(
            """
            SELECT t.relname AS tbl,
                   pg_get_constraintdef(c.oid) AS def,
                   c.conkey
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname='public' AND c.contype = 'c'
            """
        )
        col_pos = await conn.fetch(
            """
            SELECT t.relname AS tbl, a.attnum, a.attname
            FROM pg_attribute a
            JOIN pg_class t ON a.attrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname='public' AND a.attnum > 0 AND NOT a.attisdropped
            """
        )
    finally:
        await conn.close()
    columns: dict[str, set[str]] = {}
    column_meta: dict[str, dict] = {}
    for r in col_rows:
        columns.setdefault(r["table_name"], set()).add(r["column_name"])
        column_meta[f"{r['table_name']}.{r['column_name']}"] = {
            "type": r["udt_name"],
            "nullable": r["is_nullable"] == "YES",
        }
    uniques: dict[str, set[tuple[str, ...]]] = {}
    for r in unique_rows:
        uniques.setdefault(r["tbl"], set()).add(tuple(r["cols"]))
    pos_map: dict[str, dict[int, str]] = {}
    for r in col_pos:
        pos_map.setdefault(r["tbl"], {})[r["attnum"]] = r["attname"]
    checks: dict[str, set[str]] = {}
    for r in check_rows:
        cols = [pos_map.get(r["tbl"], {}).get(k) for k in (r["conkey"] or [])]
        for col in cols:
            if col:
                checks.setdefault(f"{r['tbl']}.{col}", set()).add(r["def"])
    return {
        "columns": columns,
        "column_meta": column_meta,
        "uniques": uniques,
        "checks": checks,
    }


def main() -> None:
    if not LOCK.exists():
        print(f"ERROR: lock file not found at {LOCK}", file=sys.stderr)
        sys.exit(2)
    payload = json.loads(LOCK.read_text())
    locked_tables = {k: set(v) for k, v in payload["tables"].items()}
    locked_meta = payload.get("column_meta", {})
    locked_uniques = {k: {tuple(t) for t in v} for k, v in payload.get("uniques", {}).items()}
    locked_checks = {k: set(v) for k, v in payload.get("checks", {}).items()}
    live = asyncio.run(fetch_live())

    missing_tables: list[str] = []
    missing_cols: list[tuple[str, str]] = []
    type_drift: list[tuple[str, str, str, str]] = []
    null_drift: list[tuple[str, str, bool, bool]] = []
    unique_drift: list[tuple[str, tuple[str, ...]]] = []
    check_drift: list[tuple[str, str]] = []

    for tbl, cols in locked_tables.items():
        if tbl not in live["columns"]:
            missing_tables.append(tbl)
            continue
        for c in cols:
            if c not in live["columns"][tbl]:
                missing_cols.append((tbl, c))

    for key, meta in locked_meta.items():
        if key not in live["column_meta"]:
            continue  # already counted as missing column
        live_meta = live["column_meta"][key]
        if meta.get("type") != live_meta["type"]:
            type_drift.append((key, meta.get("type"), live_meta["type"], "type"))
        if meta.get("nullable") is not None and meta["nullable"] != live_meta["nullable"]:
            null_drift.append((key, "?", meta["nullable"], live_meta["nullable"]))

    for tbl, keys in locked_uniques.items():
        live_keys = live["uniques"].get(tbl, set())
        for k in keys:
            if k not in live_keys:
                unique_drift.append((tbl, k))

    for col, defs in locked_checks.items():
        live_defs = live["checks"].get(col, set())
        for d in defs:
            if d not in live_defs:
                check_drift.append((col, d))

    print("─" * 72)
    print(f"  Schema lock check — {len(locked_tables)} tables, {len(locked_meta)} cols, "
          f"{sum(len(v) for v in locked_uniques.values())} uniques, "
          f"{sum(len(v) for v in locked_checks.values())} checks")
    print("─" * 72)

    fail = bool(missing_tables or missing_cols or type_drift or null_drift or unique_drift or check_drift)
    if not fail:
        print("✅ Live schema satisfies the lock — no drift.")
        print("─" * 72)
        print("  verdict: PASS")
        print("─" * 72)
        sys.exit(0)

    if missing_tables:
        print(f"\n❌ {len(missing_tables)} locked tables MISSING:")
        for t in sorted(missing_tables):
            print(f"  - {t}")
    if missing_cols:
        print(f"\n❌ {len(missing_cols)} locked columns MISSING:")
        for t, c in sorted(missing_cols):
            print(f"  - {t}.{c}")
    if type_drift:
        print(f"\n❌ {len(type_drift)} locked column TYPES drifted:")
        for key, expected, actual, _ in sorted(type_drift):
            print(f"  - {key}: locked={expected}  live={actual}")
    if null_drift:
        print(f"\n❌ {len(null_drift)} locked NULLABILITY flipped:")
        for key, _, expected_nullable, live_nullable in sorted(null_drift):
            l = "NULL" if expected_nullable else "NOT NULL"
            r = "NULL" if live_nullable else "NOT NULL"
            print(f"  - {key}: locked={l}  live={r}")
    if unique_drift:
        print(f"\n❌ {len(unique_drift)} locked UNIQUE keys MISSING:")
        for tbl, cols in sorted(unique_drift):
            print(f"  - {tbl}({', '.join(cols)})")
    if check_drift:
        print(f"\n❌ {len(check_drift)} locked CHECK constraints MISSING:")
        for col, d in sorted(check_drift):
            print(f"  - {col}: {d[:80]}")

    print()
    print("If the change is intentional, fix code AND regenerate the lock:")
    print("  python3 scripts/regen_schema_lock.py")
    print("─" * 72)
    print("  verdict: FAIL")
    print("─" * 72)
    sys.exit(1)


if __name__ == "__main__":
    main()
