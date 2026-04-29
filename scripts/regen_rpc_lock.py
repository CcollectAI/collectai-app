"""Snapshot all public rpc_* function signatures from the live DB and
write to scripts/rpc.lock.json. Regenerate only after intentional
function migrations land — and review the diff in PR.
"""
from __future__ import annotations
import asyncio, asyncpg, json, os, sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "rpc.lock.json"


async def main():
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr)
        sys.exit(2)
    conn = await asyncpg.connect(dsn)
    try:
        # All public rpc_* functions with their named parameters. Skip
        # overloads — record the union so the FE can call any variant.
        rows = await conn.fetch("""
            SELECT p.proname,
                   COALESCE(
                     array(SELECT unnest(p.proargnames)),
                     ARRAY[]::text[]
                   ) AS params
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public'
              AND p.proname LIKE 'rpc_%'
        """)
    finally:
        await conn.close()
    funcs: dict[str, list[str]] = {}
    for r in rows:
        existing = funcs.setdefault(r["proname"], [])
        for p in (r["params"] or []):
            if p and p not in existing:
                existing.append(p)
    payload = {
        "_about": "Frozen rpc_* function signatures. Regenerated only after intentional migrations.",
        "functions": {k: sorted(v) for k, v in funcs.items()},
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}: {len(funcs)} rpc_* functions")


asyncio.run(main())
