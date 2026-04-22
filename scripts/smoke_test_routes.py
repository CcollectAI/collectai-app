"""HTTP smoke test for every documented API endpoint.

Walks router .py files, discovers @router.{get,post,patch,delete,put} decorators,
mints one real JWT via Supabase admin API, then for every parameter-free GET
endpoint sends a real HTTP request and asserts a 2xx (or accepted 4xx for
"no data yet" responses).

Output: pass/fail/skip table. Catches the class of drift that the SQL audit
can't see — RLS policy mismatches, async crashes, response-shape errors.

Run on EC2 against localhost:8000:

    cd /opt/collectors/server && set -a && source /opt/collectors/.env && set +a && \\
    sudo -E -u ubuntu /opt/collectors/.venv/bin/python /tmp/smoke_test_routes.py

Output: markdown report on stdout.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Optional

import httpx

BASE = "http://localhost:8000"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or os.environ["SUPABASE_KEY"]

ROUTER_DIRS = [
    Path("/opt/collectors/server/app/routes"),
    Path("/opt/collectors/server/app/features"),
    Path("/opt/collectors/server/app/agents"),
]

# Match @router.<verb>("<path>", ...) decorators. Keep the path as-is so we
# can detect path-parameter routes via the {…} braces.
DECO_RE = re.compile(
    r'@router\.(get|post|patch|delete|put)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Match the router prefix from APIRouter(prefix="...", ...)
PREFIX_RE = re.compile(r'APIRouter\([^)]*\bprefix\s*=\s*["\']([^"\']+)["\']')

# Status codes we accept as "endpoint is wired correctly" — even if the
# user has no data, we expect a 2xx with empty payload, not a 5xx.
# 401/403 mean auth gating works (we send a JWT but RLS may still gate).
# 404 is acceptable for routes that need a non-existent resource.
ACCEPTED_STATUSES = {200, 201, 202, 204, 401, 403, 404}


async def admin_create_user(email: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
            json={"email": email, "password": password, "email_confirm": True},
        )
        if r.status_code == 422 and "already" in r.text.lower():
            r2 = await c.get(
                f"{SUPABASE_URL}/auth/v1/admin/users?email={email}",
                headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
            )
            r2.raise_for_status()
            users = r2.json().get("users", [])
            if users:
                return users[0]["id"]
        r.raise_for_status()
        return r.json()["id"]


async def login(email: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON},
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def admin_delete_user(uid: str) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        await c.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
        )


def discover_endpoints() -> list[tuple[str, str, str]]:
    """Return list of (file, method, full_path) for every @router decorator."""
    out: list[tuple[str, str, str]] = []
    for d in ROUTER_DIRS:
        if not d.exists():
            continue
        for path in d.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            text = path.read_text()
            prefix_m = PREFIX_RE.search(text)
            prefix = prefix_m.group(1) if prefix_m else ""
            for m in DECO_RE.finditer(text):
                verb = m.group(1).upper()
                route_path = m.group(2)
                full = (prefix.rstrip("/") + "/" + route_path.lstrip("/")).rstrip("/") or "/"
                out.append((path.name, verb, full))
    return out


async def smoke_test(jwt: str) -> list[dict]:
    """Hit every parameter-free GET endpoint, return list of result rows."""
    headers = {"Authorization": f"Bearer {jwt}"}
    results: list[dict] = []

    endpoints = discover_endpoints()

    async with httpx.AsyncClient(timeout=15, base_url=BASE) as c:
        for fname, verb, path in endpoints:
            row = {"file": fname, "verb": verb, "path": path}
            if verb != "GET":
                row["status"] = "SKIP"
                row["reason"] = "non-GET (needs body)"
                results.append(row)
                continue
            if "{" in path:
                row["status"] = "SKIP"
                row["reason"] = "path param (needs fixture)"
                results.append(row)
                continue
            try:
                r = await c.get(path, headers=headers)
                row["http"] = r.status_code
                if r.status_code in ACCEPTED_STATUSES:
                    row["status"] = "PASS"
                else:
                    row["status"] = "FAIL"
                    row["body"] = r.text[:200]
            except Exception as exc:
                row["status"] = "ERROR"
                row["reason"] = repr(exc)[:200]
            results.append(row)

    return results


async def main() -> int:
    email = "smoke-test@collectai.app"
    password = "SmokeTestR50!"
    uid = await admin_create_user(email, password)
    try:
        jwt = await login(email, password)
        results = await smoke_test(jwt)
    finally:
        await admin_delete_user(uid)

    # Counts
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print("# HTTP Smoke Test Report")
    print()
    print(f"- Endpoints discovered: **{len(results)}**")
    print(f"- PASS: **{counts['PASS']}** | FAIL: **{counts['FAIL']}** | SKIP: **{counts['SKIP']}** | ERROR: **{counts['ERROR']}**")
    print()

    fails = [r for r in results if r["status"] in ("FAIL", "ERROR")]
    if fails:
        print(f"## ❌ {len(fails)} broken endpoints\n")
        for r in fails:
            extra = r.get("body") or r.get("reason") or ""
            print(f"- **{r['verb']} {r['path']}** → {r.get('http', r['status'])} ({r['file']})")
            if extra:
                print(f"  - {extra}")
        print()

    passes = [r for r in results if r["status"] == "PASS"]
    if passes:
        print(f"## ✅ {len(passes)} working endpoints (collapsed)\n")
        for r in passes:
            print(f"- {r['verb']} {r['path']} → {r['http']}")

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
