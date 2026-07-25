#!/usr/bin/env python3
"""
Audit Row-Level Security coverage on every table carrying user_id.

Two distinct failure modes, opposite directions, both silent:

  RLS DISABLED        every authenticated user can read every other user's rows
                      through PostgREST. Nothing errors; the data just leaks.
  RLS ON, 0 POLICIES  deny-all. Every read returns [] and every write is
                      rejected. The feature looks "empty", not broken — the
                      exact shape of the silent-failure class this codebase
                      keeps producing (CLAUDE.md, "The failure mode this
                      codebase is prone to").

A grep cannot answer either question: both are properties of the LIVE database,
not of the source. Run against DB_DSN_DIRECT.

Usage:
    python3 server/scripts/audit_rls_coverage.py          # exit 1 on findings
    python3 server/scripts/audit_rls_coverage.py --json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg not installed — run on EC2 (/opt/collectors/.venv)", file=sys.stderr)
    raise SystemExit(2)

SQL = """
    SELECT t.relname                AS tbl,
           t.relrowsecurity         AS rls_enabled,
           s.n_live_tup             AS rows,
           (SELECT count(*) FROM pg_policy p WHERE p.polrelid = t.oid) AS policies
    FROM pg_class t
    JOIN pg_namespace n ON n.oid = t.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.relname = t.relname AND s.schemaname = n.nspname
    WHERE n.nspname = 'public'
      AND t.relkind = 'r'
      AND EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = t.oid AND a.attname = 'user_id' AND a.attnum > 0
      )
    ORDER BY s.n_live_tup DESC NULLS LAST
"""

# Tables where deny-all (RLS on, no policies) is correct: written only by the
# service role from the backend, never read directly by the client. An entry
# here is a decision; a missing table is a bug.
DENY_ALL_OK: dict[str, str] = {
    "subscription_events": (
        "Stripe/RevenueCat webhook audit trail. Written by the service role, "
        "which bypasses RLS; never read from the client. Deny-all is the "
        "intended posture, not a misconfiguration."
    ),
}


async def main() -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        rows = [dict(r) for r in await conn.fetch(SQL)]
    finally:
        await conn.close()

    disabled = [r for r in rows if not r["rls_enabled"]]
    deny_all = [r for r in rows if r["rls_enabled"] and r["policies"] == 0]
    unexpected_deny = [r for r in deny_all if r["tbl"] not in DENY_ALL_OK]
    stale_allow = sorted(set(DENY_ALL_OK) - {r["tbl"] for r in deny_all})

    if "--json" in sys.argv:
        print(json.dumps({
            "scanned": len(rows),
            "rls_disabled": [r["tbl"] for r in disabled],
            "deny_all_unexpected": [r["tbl"] for r in unexpected_deny],
            "stale_allowlist": stale_allow,
        }, indent=2))
    else:
        print("\n=== RLS coverage on tables with user_id ===\n")
        print(f"  scanned                    : {len(rows)}")
        print(f"  RLS disabled (LEAK)        : {len(disabled)}")
        print(f"  deny-all, unexpected       : {len(unexpected_deny)}")
        print(f"  deny-all, documented       : {len(deny_all) - len(unexpected_deny)}\n")
        for r in disabled:
            print(f"    LEAK  {r['tbl']:42} {r['rows']} rows — every user can read every row")
        for r in unexpected_deny:
            print(f"    DENY  {r['tbl']:42} {r['rows']} rows — RLS on, 0 policies: reads return [] silently")
        for t in stale_allow:
            print(f"    STALE {t} is allowlisted as deny-all but is no longer deny-all")
        if not (disabled or unexpected_deny or stale_allow):
            print("    clean — every user_id table is either policied or a documented deny-all")
        print()

    return 1 if (disabled or unexpected_deny or stale_allow) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
