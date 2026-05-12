#!/usr/bin/env python3
"""
Pre-flight: can every bake worker module actually import?

This catches the class of bug where new code ships to git but a worker
module isn't deployed to EC2 — orchestrator's `_run_worker_loop` catches
ImportError and returns cleanly, producing a silent `exc=None` dead task.

Runs as ExecStartPre on collectai-bake.service. Exits 1 with a clear
message if any module can't import, so the service refuses to start.

Usage:
  python3 scripts/preflight_worker_imports.py
  python3 scripts/preflight_worker_imports.py --json
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "server"))


def _load_manifest() -> list[tuple[str, str, str]]:
    """Return [(name, module_path, func_name), ...] from the orchestrator manifest."""
    # Import lazily so a syntax error in the orchestrator itself is also
    # caught by this pre-flight.
    from workers.bake_orchestrator import _WORKER_MANIFEST

    return [(n, m, f) for (n, m, f, _needs_db) in _WORKER_MANIFEST]


def check_imports(manifest: list[tuple[str, str, str]]) -> list[dict]:
    results = []
    for name, module_path, func_name in manifest:
        entry = {"name": name, "module": module_path, "func": func_name}
        try:
            mod = importlib.import_module(module_path)
        except Exception as e:
            entry["ok"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
            results.append(entry)
            continue

        fn = getattr(mod, func_name, None)
        if fn is None:
            entry["ok"] = False
            entry["error"] = f"module has no attribute '{func_name}'"
        elif not callable(fn):
            entry["ok"] = False
            entry["error"] = f"'{func_name}' is not callable"
        else:
            entry["ok"] = True
        results.append(entry)
    return results


def check_manifest_vs_schedules(manifest: list[tuple[str, str, str]]) -> list[dict]:
    """Catch the class of bug where a worker is in _WORKER_MANIFEST but has
    no entry (or interval=0) in SCHEDULES — orchestrator silently skips it.
    This is exactly what happened to marketplace_scrape_worker on 2026-04-17.
    """
    from app.worker_registry import SCHEDULES

    issues = []
    for name, module_path, _func in manifest:
        interval = SCHEDULES.get(name, None)
        if interval is None:
            issues.append({
                "name": name, "ok": False,
                "error": "no SCHEDULES entry — orchestrator will silently skip",
            })
        elif interval <= 0:
            issues.append({
                "name": name, "ok": False,
                "error": f"SCHEDULES[{name}]={interval} — interval must be > 0",
            })
    return issues


def check_worker_outputs_vs_schema_lock() -> list[dict]:
    """Each WORKER_OUTPUTS entry must reference a (table, timestamp_column)
    that exists in schema.lock.json.

    Catches the bug class that wasted 10 days of silent_writer probe runs
    starting 2026-05-01: the probe SQL referenced category_candidates.updated_at
    which doesn't exist, so the probe errored every cycle with a harmless-looking
    WARNING — masking real silent-writer signal behind a config typo. The
    catalog_learning_worker probe never actually checked anything.

    Expression columns (anything with non-identifier characters) are skipped
    here — they're impossible to validate against a flat column list, and the
    only one we have (aggregate_catalog_attributes' JSONB watermark expression)
    is exercised inside run_once via the probe SQL anyway.
    """
    import json
    from pathlib import Path

    issues: list[dict] = []
    try:
        from app.lib.worker_output_registry import WORKER_OUTPUTS
    except Exception as e:
        return [{"name": "<import>", "ok": False,
                 "error": f"cannot import WORKER_OUTPUTS: {e}"}]

    lock_path = Path(REPO_ROOT) / "scripts" / "schema.lock.json"
    try:
        lock = json.loads(lock_path.read_text())
    except Exception as e:
        return [{"name": "<schema.lock>", "ok": False,
                 "error": f"cannot read schema.lock.json: {e}"}]

    tables = lock.get("tables") or {}

    for worker_name, out in WORKER_OUTPUTS.items():
        col = out.timestamp_column
        # Skip expressions — they don't map to a single column name.
        if not col.replace("_", "").isalnum():
            continue
        cols = tables.get(out.table)
        if cols is None:
            issues.append({
                "name": worker_name, "ok": False,
                "error": f"WORKER_OUTPUTS table '{out.table}' missing from schema.lock",
            })
            continue
        if col not in cols:
            issues.append({
                "name": worker_name, "ok": False,
                "error": f"WORKER_OUTPUTS '{out.table}.{col}' — column not in schema.lock",
            })
    return issues


def main() -> int:
    p = argparse.ArgumentParser(description="Bake worker import pre-flight")
    p.add_argument("--json", action="store_true", help="emit JSON")
    args = p.parse_args()

    try:
        manifest = _load_manifest()
    except Exception as e:
        msg = f"Failed to load _WORKER_MANIFEST from bake_orchestrator: {e}"
        if args.json:
            print(json.dumps({"ok": False, "fatal": msg}))
        else:
            print(f"FAIL: {msg}", file=sys.stderr)
        return 1

    results = check_imports(manifest)
    failed = [r for r in results if not r["ok"]]

    try:
        schedule_issues = check_manifest_vs_schedules(manifest)
    except Exception as e:
        schedule_issues = [{"name": "<all>", "ok": False,
                            "error": f"cannot import SCHEDULES: {e}"}]

    try:
        output_issues = check_worker_outputs_vs_schema_lock()
    except Exception as e:
        output_issues = [{"name": "<all>", "ok": False,
                          "error": f"cannot validate WORKER_OUTPUTS: {e}"}]

    if args.json:
        print(json.dumps({
            "ok": not failed and not schedule_issues and not output_issues,
            "total": len(results),
            "failed": len(failed),
            "workers": results,
            "schedule_issues": schedule_issues,
            "output_issues": output_issues,
        }, indent=2))
    else:
        print("─" * 72)
        print(f"  Bake worker import pre-flight — {len(results)} workers")
        print("─" * 72)
        if not failed:
            print("✅ All workers import cleanly.")
            for r in results:
                print(f"  ✓ {r['name']:<35} {r['module']}.{r['func']}")
        else:
            print(f"❌ {len(failed)} worker(s) failed to import:")
            for r in failed:
                print(f"  ✗ {r['name']:<35} {r['module']}.{r['func']}")
                print(f"      {r['error']}")
            print()
            print("Likely cause: module not deployed to EC2, syntax error, or")
            print("missing python dependency. Fix before bake can start.")
        print("─" * 72)
        if schedule_issues:
            print(f"❌ Manifest↔SCHEDULES drift ({len(schedule_issues)}):")
            for s in schedule_issues:
                print(f"  ✗ {s['name']:<35} {s['error']}")
            print()
            print("Add a row to SCHEDULES in server/app/worker_registry.py.")
            print("─" * 72)
        if output_issues:
            print(f"❌ WORKER_OUTPUTS↔schema.lock drift ({len(output_issues)}):")
            for s in output_issues:
                print(f"  ✗ {s['name']:<35} {s['error']}")
            print()
            print("Fix the WorkerOutput entry in server/app/lib/worker_output_registry.py")
            print("or regen schema.lock.json if the column was renamed/added.")
            print("─" * 72)
        verdict_pass = not failed and not schedule_issues and not output_issues
        print(f"  verdict: {'PASS' if verdict_pass else 'FAIL'}")
        print("─" * 72)

    return 0 if (not failed and not schedule_issues and not output_issues) else 1


if __name__ == "__main__":
    sys.exit(main())
