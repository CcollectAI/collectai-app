#!/usr/bin/env python3
"""
Schema drift pre-flight check.

Catches the class of bug we hit in R46.5/R46.6 — code expects columns
on a DB table that don't exist, and PostgREST/asyncpg silently rejects
every write with PGRST204 or "column does not exist".

Each entry in EXPECTED below describes a (table, columns) pair that the
code is known to write. The script connects to the configured DB,
introspects information_schema.columns, and reports:

  - which columns are MISSING from the table (would cause writes to fail)
  - which expected columns are present (sanity)
  - which extra columns the table has (informational, not a problem)

Exit codes:
  0 — no drift, all expected columns present
  1 — drift detected (missing columns)
  2 — DB unreachable

Usage:
  python3 scripts/schema_drift_check.py                # human output
  python3 scripts/schema_drift_check.py --json         # machine-readable
  python3 scripts/schema_drift_check.py --fix-suggest  # also print ALTER TABLE statements
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# When run from the repo root, add server/ for app imports if needed
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "server"))


# Each entry is (table_name, [expected_columns], "what writes here")
# Columns are the union of what every code path writes — NOT all are
# required on every INSERT (some are optional/nullable). The check is:
# does the column exist at all? If not, writes that DO send it will 400.
EXPECTED: list[tuple[str, list[str], str]] = [
    (
        "category_items",
        [
            "id", "category", "item_key", "title", "set_code", "brand",
            "rarity", "notes", "image_url", "barcode", "attributes_json",
            "created_at", "updated_at",
        ],
        "pipelines/import_common.CatalogItem.to_row()",
    ),
    (
        "market_hits",
        [
            "provider", "listing_id", "title", "price", "currency",
            "condition", "normalized_key", "category",
        ],
        "pipelines/import_common.SupabaseIngest.upsert_market_hits()",
    ),
    (
        "user_price_alerts",
        [
            "id", "user_id", "item_id", "category", "trigger_type",
            "threshold_value", "active", "last_triggered_at",
        ],
        "workers/price_monitor_worker.py",
    ),
    (
        "alert_trigger_history",
        [
            "id", "alert_id", "user_id", "item_id", "trigger_type",
            "trigger_value", "message", "read", "created_at",
        ],
        "workers/price_monitor_worker.py + app/features/data_moat.py",
    ),
    (
        "purchase_mandates",
        [
            "id", "user_id", "name", "status", "search_query", "category",
            "max_price", "max_total_budget", "spent_total", "cooldown_hours",
            "allowed_sources", "exclude_keywords", "region", "expires_at",
            "deals_found", "deals_purchased", "created_at", "updated_at",
        ],
        "app/agents/purchase_router.py + workers/deal_discovery_worker.py",
    ),
    (
        "mandate_deals",
        [
            "id", "mandate_id", "user_id", "status", "listing_source",
            "listing_url", "listing_title", "listing_price", "listing_currency",
            "discovered_at",
        ],
        "app/agents/deal_desk_router.py + workers/deal_discovery_worker.py",
    ),
    (
        "watchlist_items",
        [
            "id", "user_id", "title", "category", "priority", "owned",
            "target_price", "currency", "image_url", "notes",
            "created_at", "updated_at",
        ],
        "app/features/watchlist_router.py",
    ),
    (
        "worker_runs",
        [
            "id", "worker_name", "status", "started_at", "finished_at",
            "metadata",
        ],
        "app/worker_registry.py (record_run) — duration stored in metadata jsonb",
    ),
    (
        "supply_snapshots",
        [
            "id", "category", "item_key", "source", "snapshot_at",
            "listing_count",
        ],
        "app/features/data_moat.py + workers",
    ),
    (
        "demand_signals",
        [
            "id", "signal_type", "category", "item_key", "user_id",
            "region", "country_code", "created_at",
        ],
        "app/features/data_moat.py.record_demand_signal()",
    ),
]


async def check_table(conn, table: str, expected_cols: list[str]) -> dict:
    """Return {missing: [], present: [], extra: [], exists: bool}."""
    table_exists = await conn.fetchval(
        "SELECT to_regclass($1) IS NOT NULL", f"public.{table}"
    )
    if not table_exists:
        return {
            "exists": False,
            "missing": expected_cols,
            "present": [],
            "extra": [],
        }
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = $1",
        table,
    )
    actual = {r["column_name"] for r in rows}
    expected = set(expected_cols)
    return {
        "exists": True,
        "missing": sorted(expected - actual),
        "present": sorted(expected & actual),
        "extra": sorted(actual - expected),
    }


async def main_async(json_mode: bool, fix_suggest: bool) -> int:
    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed (pip install asyncpg)", file=sys.stderr)
        return 2

    dsn = os.environ.get("DB_DSN", "")
    if not dsn:
        print("ERROR: DB_DSN not set in environment", file=sys.stderr)
        return 2

    try:
        conn = await asyncpg.connect(dsn, timeout=10)
    except Exception as e:
        print(f"ERROR: cannot connect to DB: {e}", file=sys.stderr)
        return 2

    results = []
    try:
        for table, expected_cols, source in EXPECTED:
            r = await check_table(conn, table, expected_cols)
            r["table"] = table
            r["source"] = source
            results.append(r)
    finally:
        await conn.close()

    total_missing = sum(len(r["missing"]) for r in results)
    missing_tables = [r for r in results if not r["exists"]]
    drifted_tables = [r for r in results if r["exists"] and r["missing"]]

    if json_mode:
        print(json.dumps({
            "ok": total_missing == 0,
            "total_expected_columns": sum(len(c) for _, c, _ in EXPECTED),
            "total_missing": total_missing,
            "tables": results,
        }, indent=2))
    else:
        print("─" * 72)
        print("  Schema drift check")
        print("─" * 72)
        if total_missing == 0:
            print("✅ All expected columns present in all tables.")
            for r in results:
                print(f"  ✓ {r['table']:30s} {len(r['present'])} columns OK")
        else:
            if missing_tables:
                print()
                print("❌ MISSING TABLES:")
                for r in missing_tables:
                    print(f"  • {r['table']:30s} (writes from: {r['source']})")
            if drifted_tables:
                print()
                print("⚠️  COLUMN DRIFT (table exists but missing expected columns):")
                for r in drifted_tables:
                    print(f"  • {r['table']:30s} missing: {', '.join(r['missing'])}")
                    print(f"    {'':30s} writes from: {r['source']}")
            if fix_suggest:
                print()
                print("── suggested ALTER TABLE statements ──")
                for r in drifted_tables:
                    cols_sql = ",\n  ".join(
                        f"ADD COLUMN IF NOT EXISTS {c} text" for c in r["missing"]
                    )
                    print(f"\nALTER TABLE public.{r['table']}")
                    print(f"  {cols_sql};")
                print()
                print("(types are placeholders — match the migration that creates each column)")

        print("─" * 72)
        print(f"  expected columns: {sum(len(c) for _, c, _ in EXPECTED)}")
        print(f"  missing total:    {total_missing}")
        print(f"  tables checked:   {len(results)}")
        print(f"  verdict:          {'PASS' if total_missing == 0 else 'FAIL'}")
        print("─" * 72)

    return 0 if total_missing == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Schema drift pre-flight check")
    p.add_argument("--json", action="store_true", help="emit JSON")
    p.add_argument("--fix-suggest", action="store_true",
                   help="print suggested ALTER TABLE statements")
    args = p.parse_args()
    return asyncio.run(main_async(args.json, args.fix_suggest))


if __name__ == "__main__":
    sys.exit(main())
