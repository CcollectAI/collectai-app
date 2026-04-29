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
        # All public rpc_* functions with their named parameters AND
        # which of those have NO default (i.e. are required at call-site).
        # PostgreSQL puts defaults at the end of the parameter list, so
        # the first (pronargs - pronargdefaults) names are required.
        rows = await conn.fetch("""
            SELECT p.proname,
                   COALESCE(
                     array(SELECT unnest(p.proargnames)),
                     ARRAY[]::text[]
                   ) AS params,
                   p.pronargs                AS nargs,
                   COALESCE(p.pronargdefaults, 0) AS ndefaults
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public'
              AND p.proname LIKE 'rpc_%'
        """)
    finally:
        await conn.close()
    funcs: dict[str, list[str]] = {}
    required: dict[str, set[str]] = {}
    for r in rows:
        names = list(r["params"] or [])
        existing = funcs.setdefault(r["proname"], [])
        for p in names:
            if p and p not in existing:
                existing.append(p)
        # First (nargs - ndefaults) named params are required. For
        # overloaded functions, intersect across overloads — a param is
        # only "required" if every overload demands it.
        n_required = max(0, int(r["nargs"]) - int(r["ndefaults"]))
        this_required = set(p for p in names[:n_required] if p)
        if r["proname"] in required:
            required[r["proname"]] &= this_required
        else:
            required[r["proname"]] = this_required
    payload = {
        "_about": "Frozen rpc_* function signatures. Regenerated only after intentional migrations.",
        "functions": {k: sorted(v) for k, v in funcs.items()},
        "required": {k: sorted(v) for k, v in required.items() if v},
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}: {len(funcs)} rpc_* functions")


asyncio.run(main())
