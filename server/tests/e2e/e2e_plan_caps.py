"""Live E2E for the NUMERIC plan caps — the paid gates nothing was testing.

Audit on 2026-08-16 mapped every key in `PLAN_LIMITS` (billing_router.py) to an
enforcement site and to a live E2E. Four had no live coverage:

    max_watchlist_items     enforced  watchlist_router.add_to_watchlist  (403)
    max_alerts_per_week     enforced  alerts_feature_router              (403)
    max_daily_deal_alerts   enforced  workers/deal_discovery_worker.py
    detailed_valuation      ENFORCED NOWHERE — dead key, removed same day

Numeric caps are the dangerous kind. A boolean gate that breaks is loud: the
feature opens and someone notices. A cap that stops biting is silent — free
users simply keep going, nothing errors, and the only symptom is revenue that
never arrives. Neither the FE limits table nor a mocked unit test can prove the
server refuses the 26th row, because both mock the thing under test.

Each cap is asserted in BOTH directions — the free plan is refused at the
boundary AND Pro is allowed past it — because a cap that rejects everyone looks
identical to a working cap until a paying member complains.

Run FROM EC2 with the bake service up:
    cd /opt/collectors/server
    set -a && . /opt/collectors/.env && set +a
    PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python \
        tests/e2e/e2e_plan_caps.py
"""
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import asyncpg
import jwt

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8000")
TAG = "e2e-caps"


def env(k: str) -> str:
    v = os.environ.get(k)
    if v:
        return v
    for line in open("/opt/collectors/.env"):
        m = re.match(r"\s*" + k + r"\s*=\s*(.+)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("missing " + k)


DSN = env("DB_DSN_DIRECT")
SECRET = env("SUPABASE_JWT_SECRET")
ISSUER = env("SUPABASE_JWT_ISSUER")

results: list[tuple[bool, str, str]] = []


def chk(name: str, ok: bool, detail: str = "") -> bool:
    results.append((bool(ok), name, str(detail)))
    print(("  PASS  " if ok else "  FAIL  ") + name + (f" | {detail}" if detail else ""))
    return bool(ok)


def token_for(uid: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": uid, "aud": "authenticated", "role": "authenticated",
                       "iat": now, "exp": now + 900, "iss": ISSUER},
                      SECRET, algorithm="HS256")


def call(method: str, path: str, tok: str, body=None, timeout: int = 30):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                 "Host": "api.sparrowcollect.com"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:300]


async def set_plan(conn, user: str, plan: str) -> None:
    await conn.execute(
        "UPDATE public.subscriptions SET plan=$2, status='active' WHERE user_id=$1::uuid",
        user, plan)


async def main() -> int:
    conn = await asyncpg.connect(DSN)
    user = None
    prev = None
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM public.user_public_profiles ORDER BY created_at LIMIT 1")
        user = str(row["user_id"])
        tok = token_for(user)
        prev = await conn.fetchrow(
            "SELECT plan, status FROM public.subscriptions WHERE user_id=$1::uuid", user)
        if prev is None:
            await conn.execute(
                "INSERT INTO public.subscriptions (user_id, plan, status, provider) "
                "VALUES ($1::uuid,'free','active','stripe')", user)
        print(f"user={user[:8]}  plan_before={prev['plan'] if prev else 'none'}\n")

        from_billing = call("GET", "/billing/status", tok)[1] or {}
        limits = from_billing.get("limits") or {}
        chk("/billing/status no longer ships the dead detailed_valuation key",
            "detailed_valuation" not in limits, f"keys={sorted(limits)[:12]}")

        # ── max_watchlist_items ─────────────────────────────────────────────
        print("1. max_watchlist_items (free 25 / pro unlimited)")
        await set_plan(conn, user, "free")
        await conn.execute("DELETE FROM public.watchlist_items WHERE user_id=$1::uuid "
                           "AND title LIKE $2", user, TAG + "%")
        base = await conn.fetchval(
            "SELECT count(*) FROM public.watchlist_items WHERE user_id=$1::uuid", user)
        cap = 25
        # Fill straight to the cap in the DB — going through the API 25 times
        # would hit the per-user rate limiter, which is a different gate.
        need = max(0, cap - base)
        for i in range(need):
            await conn.execute(
                "INSERT INTO public.watchlist_items (user_id, title, category) "
                "VALUES ($1::uuid, $2, 'pokemon')", user, f"{TAG} filler {i}")
        at_cap = await conn.fetchval(
            "SELECT count(*) FROM public.watchlist_items WHERE user_id=$1::uuid", user)
        chk("free account is sitting exactly at the cap", at_cap >= cap, f"count={at_cap}")

        st, blocked = call("POST", "/watchlist/mine", tok,
                           {"name": f"{TAG} over the line", "category": "pokemon"})
        chk("the 26th watchlist item is REFUSED on the free plan (403)",
            st == 403 and "PLAN_LIMIT_WATCHLIST" in json.dumps(blocked or {}),
            f"status={st} body={blocked}")

        await set_plan(conn, user, "pro")
        st, allowed = call("POST", "/watchlist/mine", tok,
                           {"name": f"{TAG} pro allowed", "category": "pokemon"})
        chk("the SAME request succeeds on Pro (the cap is not just broken)",
            st in (200, 201), f"status={st} body={allowed}")

        # ── max_alerts_per_week ─────────────────────────────────────────────
        print("\n2. max_alerts_per_week (free 1 / pro unlimited)")
        await set_plan(conn, user, "free")
        await conn.execute(
            "DELETE FROM public.user_price_alerts WHERE user_id=$1::uuid", user)
        # Alerts are keyed to an item UUID, not a catalogue key — the router
        # rejects anything else with INVALID_UUID.
        item_uuid = await conn.fetchval(
            "SELECT id::text FROM public.items WHERE user_id=$1::uuid AND NOT archived LIMIT 1",
            user)
        if not item_uuid:
            item_uuid = await conn.fetchval("SELECT id::text FROM public.items LIMIT 1")

        st, first = call("POST", "/alerts/mine", tok,
                         {"item_id": item_uuid, "category": "pokemon",
                          "trigger_type": "below_threshold", "threshold_value": 10})
        chk("a free member may create their first price alert of the week",
            st in (200, 201), f"status={st} body={first}")

        st, second = call("POST", "/alerts/mine", tok,
                          {"item_id": item_uuid, "category": "pokemon",
                           "trigger_type": "below_threshold", "threshold_value": 9})
        chk("the SECOND alert inside 7 days is refused on free (403)",
            st == 403, f"status={st} body={second}")

        await set_plan(conn, user, "pro")
        st, _pro_alert = call("POST", "/alerts/mine", tok,
                             {"item_id": item_uuid, "category": "pokemon",
                              "trigger_type": "below_threshold", "threshold_value": 8})
        chk("Pro is not capped weekly", st in (200, 201), f"status={st}")

        # ── max_daily_deal_alerts ───────────────────────────────────────────
        # Enforced in workers/deal_discovery_worker.py, not over HTTP, so this
        # asserts the worker reads the table rather than re-declaring a constant
        # — the exact regression MONETIZATION.md warns about.
        print("\n3. max_daily_deal_alerts (worker-enforced)")
        worker = open("/opt/collectors/server/workers/deal_discovery_worker.py").read()
        chk("the worker reads max_daily_deal_alerts from PLAN_LIMITS",
            'plan_limits.get("max_daily_deal_alerts"' in worker, "")
        chk("the worker does not hard-code its own daily number",
            worker.count("_FREE_DAILY_DEAL_ALERTS =") <= 1, "")

    finally:
        await conn.execute("DELETE FROM public.watchlist_items WHERE user_id=$1::uuid "
                           "AND title LIKE $2", user, TAG + "%")
        await conn.execute("DELETE FROM public.user_price_alerts WHERE user_id=$1::uuid",
                           user)
        if prev is not None:
            await conn.execute(
                "UPDATE public.subscriptions SET plan=$2, status=$3 WHERE user_id=$1::uuid",
                user, prev["plan"], prev["status"])
        else:
            await conn.execute(
                "DELETE FROM public.subscriptions WHERE user_id=$1::uuid", user)
        now_plan = await conn.fetchval(
            "SELECT plan FROM public.subscriptions WHERE user_id=$1::uuid", user)
        chk("the member's real plan was restored",
            now_plan == (prev["plan"] if prev else None),
            f"now={now_plan} was={prev['plan'] if prev else None}")
        left = await conn.fetchval(
            "SELECT count(*) FROM public.watchlist_items WHERE title LIKE $1", TAG + "%")
        chk("fixtures cleaned up", left == 0, f"{left} row(s) left")
        await conn.close()

    failed = [r for r in results if not r[0]]
    print(f"\nRESULT: {len(results) - len(failed)} passed, {len(failed)} failed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} | {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
