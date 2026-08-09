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
            "created_at", "updated_at", "last_scrape_attempt_at",
        ],
        "pipelines/import_common.CatalogItem.to_row() + workers/marketplace_scrape_scheduler.py",
    ),
    (
        "market_hits",
        [
            "provider", "listing_id", "title", "price", "currency",
            "condition", "normalized_key", "category", "attrs",
            "features_json", "ended_at", "seen_at", "price_eur",
            "is_listing",
            # item_ref added 2026-04-21: downstream valuation/calibration
            # join on item_ref, and the writer was silently dropping it
            # for all 16+ TCG/catalog import pipelines. See learnings.md §22,
            # §64, §65 + the root-cause essay post-write-assertion rule.
            "item_ref",
        ],
        "pipelines/import_common.SupabaseIngest.upsert_market_hits() + pipelines/import_discogs.py",
    ),
    (
        "label_events",
        [
            "id", "user_id", "item_id", "action", "payload", "created_at",
            "corrected_title", "corrected_condition", "corrected_price_eur",
            "processed_at",
        ],
        "workers/feedback_loop_worker.py + app/features/intake_router.py",
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
    (
        "notifications",
        [
            # Real columns: id, user_id, title, body, payload, type, is_read, created_at.
            # Added 2026-04-20 — silent-failure sweep found code elsewhere
            # referenced `notification_type`, which doesn't exist; the real
            # column is `type`. See FORBIDDEN_CODE_PATTERNS below.
            "id", "user_id", "title", "body", "payload", "type",
            "is_read", "created_at",
        ],
        "workers/{auction_alert,value_change,watchlist_monitor}_worker.py",
    ),
    (
        "price_ground_truths",
        [
            "id", "item_id", "actual_price", "currency", "source",
            "prediction_q50", "error_pct", "recorded_at",
        ],
        "workers/feedback_loop_worker.py + app/features/data_moat.py",
    ),
    (
        "price_predictions",
        [
            # item_ref (text) + generated_at (timestamptz) are the canonical
            # join columns. The retired `item_id` / `asof` names must never
            # reappear — see FORBIDDEN_CODE_PATTERNS. Silent-fail sweep
            # 2026-04-20 caught pp2.item_id / pp2.asof in data_moat.py.
            "id", "item_ref", "category", "q10", "q50", "q90",
            "confidence", "comps_count", "model_version", "source",
            "generated_at", "created_at", "conf_score",
            "evidence_hit_ids", "evidence_summary", "explanation",
        ],
        "workers/valuation_worker.py + app/features/predict_router.py + app/agents/dossier_agent.py",
    ),
    (
        "category_items",
        [
            # Note: `attributes_json` (jsonb) — NOT `attrs` (attrs is the
            # market_hits column). And items.attrs ≠ category_items.attributes_json.
            # The confusion between these two JSONB columns has burned us
            # multiple times (learnings #31, R50m part 3 dossier bug).
            "id", "category", "item_key", "title", "set_code", "brand",
            "rarity", "notes", "image_url", "barcode", "attributes_json",
            "created_at", "updated_at", "last_scrape_attempt_at",
            "last_crawled_at",
        ],
        "pipelines/import_common + workers/{catalog_crawler,catalog_learning,aggregate_catalog_attributes}.py",
    ),
]


# Code-level forbidden patterns — tokens that reference DB objects which do
# not exist (or have been renamed). A pre-flight grep catches these before
# they ship and silently break writes or reads. Added 2026-04-20 after 5
# days of instance-by-instance column-drift fixes — this is the structural
# remedy.
#
# Format: (regex, short description, list of path substrings to EXCLUDE).
# Excludes are substring matches against the relative path — use them to
# keep the tests that intentionally mention the forbidden name from
# tripping the check.
FORBIDDEN_CODE_PATTERNS: list[tuple[str, str, list[str]]] = [
    # SQL-column refs only — we avoid matching Python identifiers that
    # happen to spell the same word by anchoring to SQL syntax context
    # (dot-prefixed aliases, SELECT/FROM/WHERE keywords).
    (
        r"\bpp2?\.item_id\b",
        "price_predictions has no item_id column — use item_ref (text, canonical_key)",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
    (
        r"\bpp2?\.asof\b",
        "price_predictions has no asof column — use generated_at",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
    (
        # Only SQL contexts — anchoring `notification_type` to SQL keywords
        # lets us keep it out of the Python push() kwarg (which legitimately
        # takes `notification_type` as a parameter name and maps it to the
        # DB `type` column internally).
        r"(WHERE|AND|OR|SELECT|INSERT|UPDATE|SET|=)\s+[a-zA-Z_]*\.?notification_type\b",
        "notifications table has no notification_type column — use `type`",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
    (
        r"\bFROM\s+deal_candidates\b|\bINTO\s+deal_candidates\b|\bUPDATE\s+deal_candidates\b",
        "deal_candidates table does not exist — use mandate_deals or category_candidates",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
    (
        # Match worker_runs table context with ended_at in the same SQL stmt.
        # The previous `.*` variant matched plain text in comments/docstrings.
        r"FROM\s+worker_runs[^;]*ended_at|ended_at[^;]*FROM\s+worker_runs|"
        r"SET\s+ended_at\s*=\s*.*worker_runs|UPDATE\s+worker_runs[^;]*ended_at",
        "worker_runs has no ended_at column — use finished_at",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
    (
        r"category_items\.attrs\b|ci\.attrs\b",
        "category_items has no `attrs` column — use attributes_json (attrs belongs to market_hits/items)",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
    (
        # user_settings has only: user_id, currency, region, locale, created_at, updated_at.
        # No notification_preferences column exists — referencing it errored every cycle
        # for weeks in value_change_worker + insights_digest_worker. Fixed round-2 by
        # dropping the query; this pattern prevents regression.
        r"SELECT\s+notification_preferences\b|\bnotification_preferences\s+FROM\s+.*user_settings",
        "user_settings has no notification_preferences column — default to enabled in caller",
        ["schema_drift_check.py", "learnings.md", "memory"],
    ),
]


# Enum drift: (enum_name, expected_values, source)
# Code queries against enum text literals — if a value the code uses doesn't
# exist in the enum, Postgres raises "invalid input value for enum" at
# prepare time. Feedback loop R50k hit this with 'correct' vs 'correction'.
EXPECTED_ENUMS: list[tuple[str, list[str], str]] = [
    (
        "label_action",
        ["label", "correction", "confirm"],
        "workers/feedback_loop_worker.py",
    ),
]


async def check_enum(conn, enum_name: str, expected_values: list[str]) -> dict:
    """Return {missing: [], present: [], extra: [], exists: bool}."""
    rows = await conn.fetch(
        "SELECT e.enumlabel AS v FROM pg_type t "
        "JOIN pg_enum e ON t.oid = e.enumtypid WHERE t.typname = $1",
        enum_name,
    )
    if not rows:
        return {
            "exists": False,
            "missing": expected_values,
            "present": [],
            "extra": [],
        }
    actual = {r["v"] for r in rows}
    expected = set(expected_values)
    return {
        "exists": True,
        "missing": sorted(expected - actual),
        "present": sorted(expected & actual),
        "extra": sorted(actual - expected),
    }


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


def scan_forbidden_patterns() -> list[dict]:
    """Grep server/ + scripts/ for known-bad DB references. Returns a list of
    {pattern, description, hits: [{path, line, snippet}]} — empty list
    means clean. Uses ripgrep if available, falls back to a Python walker
    so the check works on minimal CI environments."""
    import re
    import subprocess

    scan_roots = [
        os.path.join(REPO_ROOT, "server"),
        os.path.join(REPO_ROOT, "scripts"),
    ]
    violations: list[dict] = []

    for regex, desc, excludes in FORBIDDEN_CODE_PATTERNS:
        hits: list[dict] = []
        # Prefer rg for speed; fall back to os.walk if rg isn't available.
        try:
            # -n line numbers, -I no-binary, --no-heading flat output,
            # -g exclude glob patterns
            cmd = ["rg", "-n", "--no-heading", "-I", "--color=never", regex] + scan_roots
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            lines = proc.stdout.splitlines()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Python fallback: walk and regex-match
            lines = []
            pat = re.compile(regex)
            for root in scan_roots:
                for dirpath, _, files in os.walk(root):
                    if any(s in dirpath for s in (".venv", "__pycache__", "node_modules")):
                        continue
                    for fn in files:
                        if not fn.endswith((".py", ".sql", ".ts", ".tsx", ".js")):
                            continue
                        full = os.path.join(dirpath, fn)
                        try:
                            with open(full, encoding="utf-8") as f:
                                for i, ln in enumerate(f, 1):
                                    if pat.search(ln):
                                        lines.append(f"{full}:{i}:{ln.rstrip()}")
                        except Exception:
                            continue

        for line in lines:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path, lineno, snippet = parts[0], parts[1], parts[2]
            rel = os.path.relpath(path, REPO_ROOT)
            if any(ex in rel for ex in excludes):
                continue
            # Skip pure comment lines (leading # or // after whitespace) —
            # documentation that mentions the bad name (e.g. a migration
            # note) is not a live reference.
            stripped = snippet.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            hits.append({"path": rel, "line": int(lineno), "snippet": stripped})

        violations.append({
            "pattern": regex,
            "description": desc,
            "hits": hits,
        })

    return violations


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
    enum_results = []
    try:
        for table, expected_cols, source in EXPECTED:
            r = await check_table(conn, table, expected_cols)
            r["table"] = table
            r["source"] = source
            results.append(r)
        for enum_name, expected_values, source in EXPECTED_ENUMS:
            r = await check_enum(conn, enum_name, expected_values)
            r["enum"] = enum_name
            r["source"] = source
            enum_results.append(r)
    finally:
        await conn.close()

    # Code-pattern scan — runs in-process, doesn't need DB.
    forbidden_violations = scan_forbidden_patterns()
    forbidden_hits = sum(len(v["hits"]) for v in forbidden_violations)

    total_missing = sum(len(r["missing"]) for r in results)
    total_missing += sum(len(r["missing"]) for r in enum_results)
    missing_tables = [r for r in results if not r["exists"]]
    drifted_tables = [r for r in results if r["exists"] and r["missing"]]

    if json_mode:
        print(json.dumps({
            "ok": total_missing == 0 and forbidden_hits == 0,
            "total_expected_columns": sum(len(c) for _, c, _ in EXPECTED),
            "total_missing": total_missing,
            "tables": results,
            "forbidden_code_patterns": forbidden_violations,
            "forbidden_hits": forbidden_hits,
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
            drifted_enums = [r for r in enum_results if r["missing"]]
            if drifted_enums:
                print()
                print("⚠️  ENUM DRIFT (enum missing expected values — code uses them in queries):")
                for r in drifted_enums:
                    print(f"  • {r['enum']:30s} missing: {', '.join(r['missing'])}")
                    print(f"    {'':30s} used by: {r['source']}")
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

        if forbidden_hits:
            print()
            print("❌ FORBIDDEN CODE PATTERNS (DB refs that will fail at runtime):")
            for v in forbidden_violations:
                if not v["hits"]:
                    continue
                print(f"  • {v['description']}")
                print(f"    pattern: {v['pattern']}")
                for h in v["hits"][:8]:
                    print(f"    {h['path']}:{h['line']}  {h['snippet'][:100]}")
                if len(v["hits"]) > 8:
                    print(f"    … and {len(v['hits']) - 8} more")
        print("─" * 72)
        print(f"  expected columns:     {sum(len(c) for _, c, _ in EXPECTED)}")
        print(f"  missing total:        {total_missing}")
        print(f"  tables checked:       {len(results)}")
        print(f"  forbidden hits:       {forbidden_hits}")
        verdict = "PASS" if (total_missing == 0 and forbidden_hits == 0) else "FAIL"
        print(f"  verdict:              {verdict}")
        print("─" * 72)

    return 0 if (total_missing == 0 and forbidden_hits == 0) else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Schema drift pre-flight check")
    p.add_argument("--json", action="store_true", help="emit JSON")
    p.add_argument("--fix-suggest", action="store_true",
                   help="print suggested ALTER TABLE statements")
    args = p.parse_args()
    return asyncio.run(main_async(args.json, args.fix_suggest))


if __name__ == "__main__":
    sys.exit(main())
