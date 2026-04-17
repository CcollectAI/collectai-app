#!/usr/bin/env python3
"""
Pre-flight: verify RLS is enabled and policies exist on critical tables.

RLS drift is an easy silent-failure mode — someone runs DROP POLICY or
ALTER TABLE DISABLE ROW LEVEL SECURITY and suddenly either (a) every
request returns empty rows, or (b) every user sees every other user's
data. Neither throws an error, so the only line of defense is a
pre-flight check that the invariants are intact.

This checks, for each critical table:
  1. Table exists
  2. RLS is enabled
  3. At least N policies exist (detects accidental DROP POLICY)

Exit codes:
  0 — invariants hold
  1 — RLS disabled or policy count below threshold
  2 — DB unreachable

Usage:
  python3 scripts/preflight_rls_check.py
  python3 scripts/preflight_rls_check.py --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Each entry: (table, min_policies, note)
# min_policies is deliberately conservative — the current baseline, not a
# target. Raising it would flag genuine policy work as "drift", so err on
# the side of catching only regressions.
RLS_INVARIANTS: list[tuple[str, int, str]] = [
    ("user_settings",     1, "per-user profile + subscription tier"),
    ("items",             4, "user collections — owner-only read/write"),
    ("watchlist_items",   2, "owner-only watchlist"),
    ("label_events",      2, "QuickScan label corrections"),
    ("predict_sessions",  2, "prediction audit trail"),
    ("alert_trigger_history", 1, "push notification audit"),
]


async def main_async(json_mode: bool) -> int:
    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed", file=sys.stderr)
        return 2

    dsn = os.environ.get("DB_DSN", "")
    if not dsn:
        print("ERROR: DB_DSN not set", file=sys.stderr)
        return 2

    try:
        conn = await asyncpg.connect(dsn, timeout=10)
    except Exception as e:
        print(f"ERROR: cannot connect to DB: {e}", file=sys.stderr)
        return 2

    results = []
    try:
        for table, min_pol, note in RLS_INVARIANTS:
            exists = await conn.fetchval(
                "SELECT to_regclass($1) IS NOT NULL", f"public.{table}"
            )
            if not exists:
                results.append({
                    "table": table, "ok": False, "reason": "table missing",
                    "note": note,
                })
                continue
            rls = await conn.fetchval(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE relname = $1 AND relnamespace = 'public'::regnamespace",
                table,
            )
            n_policies = await conn.fetchval(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = $1",
                table,
            )
            entry = {
                "table": table, "note": note,
                "rls_enabled": bool(rls),
                "policies": int(n_policies),
                "min_policies": min_pol,
            }
            if not rls:
                entry["ok"] = False
                entry["reason"] = "RLS disabled"
            elif n_policies < min_pol:
                entry["ok"] = False
                entry["reason"] = f"only {n_policies} policies (expected ≥{min_pol})"
            else:
                entry["ok"] = True
            results.append(entry)
    finally:
        await conn.close()

    failed = [r for r in results if not r.get("ok")]

    if json_mode:
        print(json.dumps({
            "ok": not failed, "total": len(results),
            "failed": len(failed), "tables": results,
        }, indent=2))
    else:
        print("─" * 72)
        print(f"  RLS invariant check — {len(results)} tables")
        print("─" * 72)
        if not failed:
            print("✅ RLS + policies intact on all critical tables.")
            for r in results:
                print(
                    f"  ✓ {r['table']:<25} rls={r['rls_enabled']}  "
                    f"policies={r['policies']} (≥{r['min_policies']})"
                )
        else:
            print(f"❌ {len(failed)} table(s) fail RLS invariants:")
            for r in failed:
                print(f"  ✗ {r['table']:<25} {r.get('reason', '?')}")
                print(f"      {r['note']}")
        print("─" * 72)
        print(f"  verdict: {'PASS' if not failed else 'FAIL'}")
        print("─" * 72)

    return 0 if not failed else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Pre-flight RLS invariant check")
    p.add_argument("--json", action="store_true")
    return asyncio.run(main_async(p.parse_args().json))


if __name__ == "__main__":
    sys.exit(main())
