"""Preflight gate: refuse bake start if router SQL references missing schema.

Wraps `audit_router_sql_drift.py --strict --allowlist=…`. Exits 0 if every
drift entry is on the allowlist (deferred work) or if there's no drift at
all. Exits non-zero on any new drift, which makes systemd refuse to start
the bake service.

Wire into collectai-bake.service via:

    ExecStartPre=/opt/collectors/.venv/bin/python /opt/collectors/scripts/preflight_router_drift.py

Added 2026-04-22 as part of the launch-readiness pass.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT = SCRIPT_DIR / "audit_router_sql_drift.py"
ALLOWLIST = SCRIPT_DIR / "router_drift_allowlist.txt"
PYTHON = sys.executable


def main() -> int:
    if not AUDIT.exists():
        print(f"ERROR: {AUDIT} not found", file=sys.stderr)
        return 1
    if not os.environ.get("DB_DSN_DIRECT") and not os.environ.get("DB_DSN"):
        print("ERROR: DB_DSN_DIRECT or DB_DSN must be set for the drift audit", file=sys.stderr)
        return 1

    cmd = [
        PYTHON, str(AUDIT),
        "--strict",
        "--allowlist", str(ALLOWLIST),
    ]
    print(f"[preflight_router_drift] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Always echo the report so the failure context is visible in journalctl.
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    if result.returncode == 0:
        print("[preflight_router_drift] PASS — no non-allowlisted drift")
        return 0

    print(
        "[preflight_router_drift] FAIL — fix the drift above OR add the entry to "
        f"{ALLOWLIST.name} if intentionally deferred",
        file=sys.stderr,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
