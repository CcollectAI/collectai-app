"""Post-start smoke test: hits every parameter-free GET endpoint.

Runs as `ExecStartPost` after collectai-bake.service starts. Waits up to
60s for `/healthz` to return 200, then runs `smoke_test_routes.py` and
fires a Telegram alert if any endpoint returns an unexpected 5xx.

Failure here does NOT bring the service down (the service is already up).
The point is to surface response-shape regressions within seconds of a
restart, not to gate startup.

Added 2026-04-22 as part of the launch-readiness pass.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

SCRIPT_DIR = Path(__file__).resolve().parent
SMOKE = SCRIPT_DIR / "smoke_test_routes.py"
PYTHON = sys.executable
HEALTHZ = "http://127.0.0.1:8000/healthz"
WAIT_SECS = 60
POLL_INTERVAL = 2.0

# Re-use the bake-side telegram helper so alerts land in the same channel
# as the orchestrator's other pages.
def _send_telegram(msg: str) -> None:
    """Page the ops channel.

    Until 2026-09-01 this imported `send_telegram_alert`, which has never
    existed in app.lib.telegram_ops -- the function is `send_ops_alert`, and it
    is ASYNC, so even the correct name called synchronously would have built a
    coroutine and dropped it. Both mistakes landed in the bare `except` below
    and became one stderr line, so every postflight page since this script was
    written alerted nobody. Caught live on 2026-09-01, where bake.log carried
    "PAGED - 1 real 5xx endpoints" immediately after
    "telegram fallback failed: ImportError(...)".
    """
    try:
        sys.path.insert(0, "/opt/collectors/server")
        import asyncio
        from app.lib.telegram_ops import configured, send_ops_alert  # type: ignore
        if not configured():
            print("[postflight_smoke_test] telegram not configured - page NOT sent",
                  file=sys.stderr)
            return
        ok = asyncio.run(send_ops_alert(msg, title="Postflight smoke test"))
        if not ok:
            print("[postflight_smoke_test] telegram send returned False - page NOT sent",
                  file=sys.stderr)
    except Exception as exc:
        print(f"[postflight_smoke_test] telegram fallback failed: {exc!r}", file=sys.stderr)


def wait_for_healthz(deadline_secs: int) -> bool:
    """Block until /healthz returns 200 or deadline passes."""
    start = time.monotonic()
    while time.monotonic() - start < deadline_secs:
        try:
            with urlopen(HEALTHZ, timeout=2) as r:
                if r.status == 200:
                    return True
        except URLError:
            pass
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return False


def main() -> int:
    if not SMOKE.exists():
        print(f"ERROR: {SMOKE} not found", file=sys.stderr)
        return 0  # not a startup blocker
    if not wait_for_healthz(WAIT_SECS):
        print(f"[postflight_smoke_test] /healthz never came up in {WAIT_SECS}s — skipping", file=sys.stderr)
        return 0

    cmd = [PYTHON, str(SMOKE)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    out = result.stdout or ""
    sys.stdout.write(out)
    if result.stderr:
        sys.stderr.write(result.stderr)

    # Parse the FAIL count from the report header.
    fail_count = 0
    m = re.search(r"FAIL:\s*\*\*(\d+)\*\*", out)
    if m:
        fail_count = int(m.group(1))

    # Count REAL failures (5xx) — the smoke script counts 401/403/404/422 as
    # acceptable, but 4xx that aren't auth gates are still in FAIL bucket. We
    # only want to page on 500s. Filter for "→ 5" in the broken-endpoints list.
    real_fails = re.findall(r"→ (5\d\d) ", out)
    if real_fails:
        msg = (
            f"⚠️ POST-START SMOKE: {len(real_fails)} 5xx endpoint(s) after bake restart.\n"
            f"Codes: {sorted(set(real_fails))}\n"
            "See systemd journal for full report."
        )
        _send_telegram(msg)
        print(f"[postflight_smoke_test] PAGED — {len(real_fails)} real 5xx endpoints", file=sys.stderr)
    else:
        print(f"[postflight_smoke_test] OK — no 5xx (FAIL bucket={fail_count} is auth/missing-param noise)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
