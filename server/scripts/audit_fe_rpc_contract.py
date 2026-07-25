#!/usr/bin/env python3
"""
Audit every supabase.rpc() the FRONTEND calls against the live database.

Two failure modes, both silent from the app's side:

  function missing      PostgREST returns 404
  no EXECUTE grant      PostgREST returns 42501 for role 'authenticated'

Either way the caller gets an error object it typically logs and swallows, and
the feature returns nothing. The FE typechecks fine — `supabase.rpc('name')`
takes a string, so a renamed or never-shipped function is invisible until a user
reports that a button does nothing.

The existing preflight_rpc_lock gate covers RPCs the SERVER calls. Nothing
covered the client's, which are a separate set: presence, typing, blocking, DM
requests, build-paint projects, catalog ownership.

Grants matter as much as existence. A function created without
`GRANT EXECUTE ... TO authenticated` exists in pg_proc and still fails for every
real user, while working perfectly for the service role a migration script runs
as — so it passes a naive existence check and a manual test done as admin.

Usage:  python3 server/scripts/audit_fe_rpc_contract.py [--json]
Requires DB_DSN_DIRECT and the repo checked out (it greps the FE source).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg not installed — run on EC2 (/opt/collectors/.venv)", file=sys.stderr)
    raise SystemExit(2)

REPO = Path(__file__).resolve().parents[2]
RPC_RE = re.compile(r"""\.rpc\(\s*['"`]([a-z0-9_]+)['"`]""")


def fe_rpc_names() -> dict[str, list[str]]:
    """rpc name -> call sites, from app/ and src/."""
    out: dict[str, list[str]] = {}
    for root in ("app", "src"):
        base = REPO / root
        if not base.exists():
            continue
        for path in list(base.rglob("*.ts")) + list(base.rglob("*.tsx")):
            if "__tests__" in str(path):
                continue
            try:
                src = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in RPC_RE.finditer(src):
                loc = f"{path.relative_to(REPO)}:{src[:m.start()].count(chr(10)) + 1}"
                out.setdefault(m.group(1), []).append(loc)
    return out


async def main() -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    calls = fe_rpc_names()
    if not calls:
        print("no supabase.rpc() calls found in app/ or src/ — is the repo present?", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        findings = []
        for name in sorted(calls):
            rows = await conn.fetch(
                """
                SELECT has_function_privilege('authenticated', p.oid, 'EXECUTE') AS auth_ok
                FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace
                WHERE ns.nspname = 'public' AND p.proname = $1
                """,
                name,
            )
            if not rows:
                findings.append((name, "does not exist -> PostgREST 404"))
            elif not any(r["auth_ok"] for r in rows):
                findings.append((name, "no EXECUTE grant for 'authenticated' -> 42501"))
    finally:
        await conn.close()

    if "--json" in sys.argv:
        print(json.dumps({"checked": len(calls),
                          "findings": [{"rpc": n, "problem": w, "sites": calls[n]}
                                       for n, w in findings]}, indent=2))
    else:
        print("\n=== frontend supabase.rpc() vs live database ===\n")
        print(f"  distinct rpc names called by the FE : {len(calls)}")
        print(f"  callable by role 'authenticated'    : {len(calls) - len(findings)}")
        print(f"  BROKEN                              : {len(findings)}\n")
        for name, why in findings:
            print(f"    {name}: {why}")
            for site in calls[name][:4]:
                print(f"        {site}")
            print()
        if not findings:
            print("    clean — every FE rpc exists and is executable by authenticated\n")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
