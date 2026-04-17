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

    if args.json:
        print(json.dumps({
            "ok": not failed and not schedule_issues,
            "total": len(results),
            "failed": len(failed),
            "workers": results,
            "schedule_issues": schedule_issues,
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
        print(f"  verdict: {'PASS' if (not failed and not schedule_issues) else 'FAIL'}")
        print("─" * 72)

    return 0 if (not failed and not schedule_issues) else 1


if __name__ == "__main__":
    sys.exit(main())
