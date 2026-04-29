"""Regenerate schema.lock.json from the live DB. Run this whenever a
schema change is intentional and approved (after migrations land).
The lock file is committed to the repo and acts as the single source
of truth that BOTH the FE drift scanner AND the DB drift gate compare
against.

The lock now carries:
  tables[table]            — ordered list of column names (back-compat)
  column_meta[table.col]   — {type, nullable, default} per column
  uniques[table]           — unique-key column tuples (constraint or
                             unique index); UPSERT/ON CONFLICT depends
                             on these staying put
  checks[table.col]        — list of CHECK constraint expressions
                             touching this column

Adding new tables/columns is silent (lock isn't violated). DROPS,
RENAMES, type changes, NOT NULL flips, unique-key changes, and check
mutations all flag in `preflight_schema_lock.py` and the FE drift
scanner.
"""
import asyncio, asyncpg, json, os, sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "scripts" / "schema.lock.json"


async def main():
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr)
        sys.exit(2)
    conn = await asyncpg.connect(dsn)
    try:
        # Disable statement timeout — information_schema queries on a
        # heavily-partitioned DB can exceed the pooler/server default.
        await conn.execute("SET statement_timeout = 0")
        col_rows = await conn.fetch(
            """
            SELECT c.relname     AS table_name,
                   a.attname     AS column_name,
                   t.typname     AS udt_name,
                   t.typname     AS data_type,
                   CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable,
                   pg_get_expr(ad.adbin, ad.adrelid) AS column_default,
                   a.attnum
            FROM pg_attribute a
            JOIN pg_class c     ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            JOIN pg_type t      ON a.atttypid = t.oid
            LEFT JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
            WHERE n.nspname = 'public'
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND c.relkind IN ('r','p','v','m','f')
            ORDER BY c.relname, a.attnum
            """
        )
        # Unique constraints AND unique indexes (upserts use both)
        unique_rows = await conn.fetch(
            """
            SELECT t.relname AS table_name,
                   i.relname AS index_name,
                   array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS cols
            FROM pg_class t
            JOIN pg_namespace n ON t.relnamespace = n.oid
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE n.nspname='public' AND ix.indisunique
            GROUP BY t.relname, i.relname
            ORDER BY t.relname, i.relname
            """
        )
        check_rows = await conn.fetch(
            """
            SELECT t.relname AS table_name,
                   pg_get_constraintdef(c.oid) AS def,
                   c.conname,
                   c.conkey
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname='public' AND c.contype = 'c'
            ORDER BY t.relname, c.conname
            """
        )
        # Map conkey (column nums) → column names per table for CHECKs
        col_pos = await conn.fetch(
            """
            SELECT t.relname AS table_name, a.attnum, a.attname
            FROM pg_attribute a
            JOIN pg_class t ON a.attrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname='public' AND a.attnum > 0 AND NOT a.attisdropped
            """
        )
    finally:
        await conn.close()

    tables: dict[str, list[str]] = {}
    column_meta: dict[str, dict] = {}
    for r in col_rows:
        tbl = r["table_name"]
        col = r["column_name"]
        tables.setdefault(tbl, []).append(col)
        column_meta[f"{tbl}.{col}"] = {
            "type": r["udt_name"],
            "nullable": r["is_nullable"] == "YES",
        }
        if r["column_default"] is not None:
            column_meta[f"{tbl}.{col}"]["default"] = r["column_default"]

    uniques: dict[str, list[list[str]]] = {}
    for r in unique_rows:
        uniques.setdefault(r["table_name"], []).append(list(r["cols"]))

    pos_map: dict[str, dict[int, str]] = {}
    for r in col_pos:
        pos_map.setdefault(r["table_name"], {})[r["attnum"]] = r["attname"]

    checks: dict[str, list[str]] = {}
    for r in check_rows:
        tbl = r["table_name"]
        cols = [pos_map.get(tbl, {}).get(k) for k in (r["conkey"] or [])]
        for col in cols:
            if col:
                checks.setdefault(f"{tbl}.{col}", []).append(r["def"])

    payload = {
        "_about": "Frozen public schema. Regenerated only after intentional migrations.",
        "tables": tables,
        "column_meta": column_meta,
        "uniques": {k: sorted(v) for k, v in uniques.items()},
        "checks": checks,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"wrote {OUT}: {len(tables)} tables, "
        f"{len(column_meta)} columns, "
        f"{sum(len(v) for v in uniques.values())} unique keys, "
        f"{sum(len(v) for v in checks.values())} check constraints"
    )


asyncio.run(main())
