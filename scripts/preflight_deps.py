#!/usr/bin/env python3
"""
Pre-flight: verify Python dependencies are installed + internally consistent.

Catches two classes of bug:
  1. `pip check` failure — installed packages have conflicting requirements
     (e.g. someone upgraded asyncpg and broke sqlalchemy)
  2. Critical runtime imports missing — a known list of imports the bake
     requires. `pip check` doesn't catch "package was never installed",
     so we also do a try-import gate for critical libs.

Exit codes:
  0 — deps consistent, critical imports present
  1 — drift detected

Usage:
  python3 scripts/preflight_deps.py
"""
from __future__ import annotations

import importlib
import subprocess
import sys


# Critical runtime deps — must be importable or the bake can't function.
# Keep this list tight; it's not a replacement for requirements.txt,
# it's a smoke test for the packages workers use at runtime.
CRITICAL_IMPORTS: list[str] = [
    "asyncpg",       # DB
    "httpx",         # HTTP client + telegram ops alerts
    "fastapi",
    "uvicorn",
    "pydantic",
    "boto3",         # S3 / model artifacts
    "sklearn",       # Ridge models
    "numpy",
    "PIL",           # Pillow — image handling
    # Sentry is intentionally omitted — main.py + request_id.py both
    # guard `import sentry_sdk` with try/except ImportError so it's optional.
    # `telegram` pip package is not used; telegram_ops.py hits the API via httpx.
]


def check_pip() -> tuple[bool, str]:
    """Run `pip check` and return (ok, output)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True, text=True, timeout=30,
        )
        ok = result.returncode == 0
        out = (result.stdout + result.stderr).strip()
        return ok, out
    except subprocess.TimeoutExpired:
        return False, "pip check timed out after 30s"
    except Exception as e:
        return False, f"pip check failed to run: {e}"


def check_critical_imports() -> list[dict]:
    results = []
    for mod in CRITICAL_IMPORTS:
        entry = {"module": mod}
        try:
            importlib.import_module(mod)
            entry["ok"] = True
        except Exception as e:
            entry["ok"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
        results.append(entry)
    return results


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Pre-flight dependency check")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    pip_ok, pip_out = check_pip()
    import_results = check_critical_imports()
    import_failed = [r for r in import_results if not r["ok"]]

    verdict_ok = pip_ok and not import_failed

    if args.json:
        import json
        print(json.dumps({
            "ok": verdict_ok,
            "pip_check": {"ok": pip_ok, "output": pip_out},
            "imports": import_results,
        }, indent=2))
    else:
        print("─" * 72)
        print("  Python dependency pre-flight")
        print("─" * 72)
        if pip_ok:
            print("✅ pip check clean")
        else:
            print("❌ pip check FAILED:")
            for line in pip_out.splitlines():
                print(f"    {line}")
        print()
        if not import_failed:
            print(f"✅ All {len(import_results)} critical imports available")
        else:
            print(f"❌ {len(import_failed)}/{len(import_results)} critical imports missing:")
            for r in import_failed:
                print(f"    ✗ {r['module']}: {r['error']}")
            print()
            print("Fix: `pip install -r requirements.txt` on this host.")
        print("─" * 72)
        print(f"  verdict: {'PASS' if verdict_ok else 'FAIL'}")
        print("─" * 72)

    return 0 if verdict_ok else 1


if __name__ == "__main__":
    sys.exit(main())
