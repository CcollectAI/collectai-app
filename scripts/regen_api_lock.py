"""Snapshot every FastAPI route into scripts/api.lock.json.

Reads the **app object**, not the source text.

WHY (2026-09-07): this script used to regex the decorators out of
`server/**/*.py`. That models `@router.get("/x")` plus a router's own
`prefix=`, but it cannot model `include_router` — so it was blind to
`main.py`'s `_v1 = APIRouter(prefix="/v1")` block, which re-mounts ~40
feature routers under `/v1`. Running it produced **339** routes where the
app really serves **555**, silently dropping 233 live `/v1/...` paths.

That mattered because `audit_fe_api_drift.py` treats "not in the lock" as
drift. A lock missing a third of the API is not a smaller gate, it is a
**wrong** one: it would have reported real routes as drift and, worse,
stopped protecting every `/v1` path.

Importing the app is exact by construction — prefixes, nested
`include_router`, and mounts all resolve the way FastAPI itself resolves
them. Importing does not start a server or touch the database: the pool is
created in the lifespan handler, which only runs under uvicorn.

    .venv/bin/python scripts/regen_api_lock.py

Needs the server's dependencies importable. CI never runs this — CI runs
the audit, which only reads the JSON.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
OUT = ROOT / "scripts" / "api.lock.json"

# Verbs FastAPI adds automatically; they are not part of the API surface
# the FE calls, and including them would double the lock for no signal.
SKIP_METHODS = {"HEAD", "OPTIONS"}


def _location(endpoint) -> tuple[str, int]:
    """Best-effort source location for a route handler."""
    try:
        code = endpoint.__code__
        return str(Path(code.co_filename).resolve().relative_to(ROOT)), code.co_firstlineno
    except Exception:
        return "", 0


def main() -> int:
    sys.path.insert(0, str(SERVER))
    os.chdir(SERVER)
    try:
        from main import app  # noqa: WPS433 — deliberate late import
    except Exception as exc:
        # Fail CLOSED. Writing a partial lock is how a gate silently shrinks:
        # every route that failed to import would read as FE drift.
        print(f"FATAL: could not import the FastAPI app: {type(exc).__name__}: {exc}")
        print("The lock was NOT written. Fix the import and re-run.")
        return 2

    routes: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for r in app.routes:
        path = getattr(r, "path", None)
        if not path:
            continue
        for method in sorted(getattr(r, "methods", None) or []):
            if method in SKIP_METHODS:
                continue
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            f, line = _location(getattr(r, "endpoint", None))
            routes.append({"method": method, "path": path, "file": f, "line": line})

    if len(routes) < 400:
        # A sanity floor, not a style check. The regex version silently
        # produced 339 and looked plausible; a number this far below the
        # known surface means the import lost routers, and shipping it
        # would blind the drift gate.
        print(f"FATAL: only {len(routes)} routes found; expected 500+.")
        print("Something did not import. The lock was NOT written.")
        return 2

    routes.sort(key=lambda x: (x["method"], x["path"]))
    OUT.write_text(
        json.dumps(
            {
                "_about": (
                    "Frozen FastAPI route table, read from the app object by "
                    "scripts/regen_api_lock.py. Regenerate only after intentional "
                    "route changes."
                ),
                "routes": routes,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"wrote {OUT}: {len(routes)} unique routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
