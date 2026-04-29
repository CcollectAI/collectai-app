"""Regenerate schema.lock.json from the live DB. Run this whenever a
schema change is intentional and approved (after migrations land).
The lock file is committed to the repo and acts as the single source
of truth that BOTH the FE drift scanner AND the DB drift gate compare
against.
"""
import asyncio, asyncpg, json, os, sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "scripts" / "schema.lock.json"

async def main():
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr); sys.exit(2)
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='public' "
            "ORDER BY table_name, ordinal_position"
        )
    finally:
        await conn.close()
    cols: dict[str, list[str]] = {}
    for r in rows:
        cols.setdefault(r["table_name"], []).append(r["column_name"])
    payload = {
        "_about": "Frozen public schema. Regenerated only after intentional migrations.",
        "_generated_at": "FROZEN",
        "tables": cols,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}: {len(cols)} tables")

asyncio.run(main())
