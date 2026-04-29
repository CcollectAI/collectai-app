#!/usr/bin/env python3
"""Preflight gate: every locked rpc_* function must still exist on
the live DB with the same parameter names.

The lock file (scripts/rpc.lock.json) is the contract between the FE
and the DB for RPCs. Adding new functions or new optional parameters
is fine and silent. DROPPING a function or RENAMING a parameter is
the bug class that took DMs offline for weeks before today's sweep —
this gate makes that crash on `systemctl restart` instead of becoming
a silent FE fail at runtime.

Exit codes:
  0 — lock satisfied (live ⊇ lock)
  1 — drift: a locked function is missing OR a locked param is gone
  2 — DB unreachable, lock file missing, or other config error
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

LOCK = Path(__file__).resolve().parent / "rpc.lock.json"


async def fetch_live() -> dict[str, set[str]]:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr)
        sys.exit(2)
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT p.proname, "
            "       COALESCE(array(SELECT unnest(p.proargnames)), ARRAY[]::text[]) AS params "
            "FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid "
            "WHERE n.nspname='public' AND p.proname LIKE 'rpc_%'"
        )
    finally:
        await conn.close()
    out: dict[str, set[str]] = {}
    for r in rows:
        existing = out.setdefault(r["proname"], set())
        for p in (r["params"] or []):
            if p:
                existing.add(p)
    return out


def main() -> None:
    if not LOCK.exists():
        print(f"ERROR: lock file not found at {LOCK}", file=sys.stderr)
        sys.exit(2)
    payload = json.loads(LOCK.read_text())
    locked = {k: set(v) for k, v in payload["functions"].items()}
    live = asyncio.run(fetch_live())

    missing_fns: list[str] = []
    missing_params: list[tuple[str, str]] = []
    for fn, params in locked.items():
        if fn not in live:
            missing_fns.append(fn)
            continue
        for p in params:
            if p not in live[fn]:
                missing_params.append((fn, p))

    print("─" * 72)
    print(f"  RPC lock check — {len(locked)} functions")
    print("─" * 72)

    if not missing_fns and not missing_params:
        print(f"✅ Live DB satisfies the rpc lock ({len(locked)} functions, all params present).")
        print("─" * 72)
        print("  verdict: PASS")
        print("─" * 72)
        sys.exit(0)

    if missing_fns:
        print(f"\n❌ {len(missing_fns)} locked rpc_* functions MISSING from live DB:")
        for n in sorted(missing_fns):
            print(f"  - {n}")
    if missing_params:
        print(f"\n❌ {len(missing_params)} locked params MISSING from live DB:")
        for n, p in sorted(missing_params):
            print(f"  - {n}({p})")
    print()
    print("If the change is intentional, update FE callers to stop using the")
    print("dropped name AND regenerate the lock: `python3 scripts/regen_rpc_lock.py`.")
    print("─" * 72)
    print("  verdict: FAIL")
    print("─" * 72)
    sys.exit(1)


if __name__ == "__main__":
    main()
