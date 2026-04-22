#!/usr/bin/env python3
"""Sequential runner for every E2E script in this directory.

Sleeps 5s between scripts so per-user rate limits (set per scope at
20-30 req/min) don't bleed across tests. Reports a per-script PASS/FAIL
table at the end. Exit code = number of failed scripts (0 on full pass).

Usage:
    cd /opt/collectors/server
    set -a && source /opt/collectors/.env && set +a
    sudo -E -u ubuntu /opt/collectors/.venv/bin/python tests/e2e/run_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

E2E_DIR = Path(__file__).resolve().parent
INTER_TEST_PAUSE = 5.0
PER_TEST_TIMEOUT = 180  # seconds; marketplace search can take 90s+

# Order matters slightly — feature flows first (chat, deals), then user writes,
# then marketplace (slow), then read-only audits. Pre-existing scripts last.
ORDER = [
    "e2e_chat.py",
    "e2e_deal_desk.py",
    "e2e_deal_desk_full.py",
    "e2e_deal_desk_edges.py",
    "e2e_user_writes.py",
    "e2e_user_writes2.py",
    "e2e_billing.py",
    "e2e_events_social.py",
    "e2e_misc.py",
    "e2e_summary_notif.py",
    "e2e_marketplace.py",
    "e2e_v2.py",
    "e2e_pro_features.py",
    "e2e_bulk.py",
    "e2e_analytics.py",
]


def main() -> int:
    py = sys.executable
    results: list[tuple[str, int, float]] = []

    discovered = {p.name for p in E2E_DIR.glob("e2e_*.py")}
    queue = [n for n in ORDER if n in discovered] + sorted(discovered - set(ORDER))

    for i, name in enumerate(queue):
        print(f"\n{'='*70}\n[{i+1}/{len(queue)}] {name}\n{'='*70}")
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                [py, str(E2E_DIR / name)],
                timeout=PER_TEST_TIMEOUT,
                env=os.environ.copy(),
            )
            results.append((name, r.returncode, time.monotonic() - t0))
        except subprocess.TimeoutExpired:
            results.append((name, -1, PER_TEST_TIMEOUT))
            print(f"  ✗ TIMEOUT after {PER_TEST_TIMEOUT}s", file=sys.stderr)
        except Exception as exc:
            results.append((name, -2, time.monotonic() - t0))
            print(f"  ✗ ERROR: {exc!r}", file=sys.stderr)

        if i + 1 < len(queue):
            time.sleep(INTER_TEST_PAUSE)

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    failed = 0
    for name, code, dur in results:
        mark = "✓" if code == 0 else "✗"
        if code != 0:
            failed += 1
        print(f"  {mark} [exit={code:>3}] {dur:>6.1f}s  {name}")
    print(f"\n{len(results) - failed}/{len(results)} scripts passed")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
