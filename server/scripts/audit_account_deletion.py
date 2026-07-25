#!/usr/bin/env python3
"""
Audit DELETE /account coverage against the LIVE schema.

Why this exists: on 2026-07-25 the live DB had 126 BASE TABLES carrying a
user_id column. 38 had an ON DELETE CASCADE, 9 were listed in
account_router._ALLOWED_TABLES -- and the remaining 80 were never touched.
DELETE /account returned {"success": true} while leaving the user's chat
messages, item images, push tokens, marketplace defaults, scan history and
privacy settings in the database.

Nothing caught it because every existing check asks a STRUCTURAL question
("does the endpoint work?", "does it return 200?"). Deletion coverage is a
question about VALUES -- which tables exist, right now, with a user_id -- and
only comparing against the live schema answers it.

Every table with user_id must be in exactly one of three buckets:
  1. ON DELETE CASCADE          removed automatically with the profile row
  2. _ALLOWED_TABLES            deleted explicitly
  3. _RETAINED_TABLES           deliberately kept, WITH a written reason
Anything in none of them is a silent gap and fails this audit. A newly added
table therefore cannot reopen the hole without someone making a decision.

Usage:
    python3 server/scripts/audit_account_deletion.py           # report, exit 1 on gaps
    python3 server/scripts/audit_account_deletion.py --json    # machine readable
Requires DB_DSN_DIRECT (run on EC2, or with the direct DSN exported).
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg not installed — run this on EC2 (/opt/collectors/.venv)", file=sys.stderr)
    raise SystemExit(2)

ROUTER = Path(__file__).resolve().parents[1] / "app" / "routes" / "account_router.py"

BASE_TABLES_SQL = """
    SELECT c.table_name
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_name = c.table_name AND t.table_schema = c.table_schema
    WHERE c.table_schema = 'public'
      AND c.column_name = 'user_id'
      AND t.table_type = 'BASE TABLE'
"""

CASCADE_SQL = """
    SELECT DISTINCT tc.table_name, rc.delete_rule
    FROM information_schema.table_constraints tc
    JOIN information_schema.referential_constraints rc
      ON rc.constraint_name = tc.constraint_name
    JOIN information_schema.key_column_usage kcu
      ON kcu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND kcu.column_name = 'user_id'
"""

# Partition children are covered by their parent; auditing them separately
# would report the same gap N times and train the reader to ignore it.
PARTITION_PREFIXES = ("market_hits_y", "market_hits_default", "market_hits_archive")


def _parse_router() -> tuple[set[str], dict[str, str]]:
    """Read the two lists out of account_router.py without importing it."""
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    allowed: set[str] = set()
    retained: dict[str, str] = {}
    for node in ast.walk(tree):
        # `_RETAINED_TABLES: dict[str, str] = {...}` is an AnnAssign, not an
        # Assign — handling only Assign silently parsed it as empty, which made
        # the audit report the two retained tables as gaps.
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "_ALLOWED_TABLES" and isinstance(node.value, (ast.Tuple, ast.List)):
                allowed = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
            elif target.id == "_RETAINED_TABLES" and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant):
                        retained[k.value] = v.value if isinstance(v, ast.Constant) else "(no reason)"
    return allowed, retained


async def main() -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        base = {r["table_name"] for r in await conn.fetch(BASE_TABLES_SQL)}
        cascade = {r["table_name"] for r in await conn.fetch(CASCADE_SQL) if r["delete_rule"] == "CASCADE"}
    finally:
        await conn.close()

    allowed, retained = _parse_router()
    base = {t for t in base if not t.startswith(PARTITION_PREFIXES)}

    gaps = sorted(base - cascade - allowed - set(retained))
    stale_allowed = sorted(allowed - base)
    stale_retained = sorted(set(retained) - base)
    unreasoned = sorted(t for t, why in retained.items() if not why or why == "(no reason)")

    if "--json" in sys.argv:
        print(json.dumps({
            "with_user_id": len(base), "cascade": len(base & cascade),
            "deleted": len(base & allowed), "retained": len(base & set(retained)),
            "gaps": gaps, "stale_allowed": stale_allowed, "stale_retained": stale_retained,
        }, indent=2))
    else:
        print("\n=== DELETE /account coverage (live schema) ===\n")
        print(f"  base tables with user_id : {len(base)}")
        print(f"    ON DELETE CASCADE      : {len(base & cascade)}")
        print(f"    explicitly deleted     : {len(base & allowed)}")
        print(f"    deliberately retained  : {len(base & set(retained))}")
        print(f"    UNCOVERED (gap)        : {len(gaps)}\n")
        for t in gaps:
            print(f"    GAP  {t}  — user data survives account deletion")
        for t in stale_allowed:
            print(f"    STALE  {t} is listed for deletion but no longer exists")
        for t in stale_retained:
            print(f"    STALE  {t} is listed as retained but no longer exists")
        for t in unreasoned:
            print(f"    NO REASON  {t} is retained without a written justification")
        print()

    return 1 if (gaps or stale_allowed or stale_retained or unreasoned) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
