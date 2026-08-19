"""Live E2E for the two agent-backed chains that had none.

1. DEAL AGENT — mandate lifecycle and the `canonical_key` contract
   (docs/API.md "Smart Deal Agent"). The unit tests around this mock asyncpg,
   so they cannot catch the thing that actually breaks: the key is resolved at
   WRITE time against `category_items`, and the mandate stores a NAMESPACED
   `canonical_ref` derived from a BARE key. That resolution is pure DB.

2. SET COMPLETENESS — the chain behind app/sets-to-complete.tsx
   (docs/HELP_AND_GUIDES.md "Sets to complete"). This screen was empty for
   every account, always, because `/portfolio/items` returned no set fields, so
   `expectedCount` was null and every set silently scored 100%. Nothing errored.
   The regression test for that has to assert the JOIN delivers `set_size` —
   asserting a 200 proves nothing, which is exactly how it shipped broken.

Run FROM EC2 with the bake service up:
    cd /opt/collectors/server
    set -a && . /opt/collectors/.env && set +a
    PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python \
        tests/e2e/e2e_deal_agent_and_sets.py

Everything it writes is tagged and removed in a finally block:
    mandates      name LIKE 'e2e-agent-%'
    sets          metadata->>'seed' = 'e2e-agent'
    items         source = 'seed:e2e-agent'
"""
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

import asyncpg
import jwt

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8000")
TAG = "e2e-agent"


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


async def main() -> int:
    conn = await asyncpg.connect(DSN)
    user = None
    set_id = None
    granted_pro = False
    prev_sub = None
    made_items: list[str] = []
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM public.user_public_profiles ORDER BY created_at LIMIT 1")
        user = str(row["user_id"])
        tok = token_for(user)
        print(f"user={user[:8]}\n")

        # ── 1. DEAL AGENT ────────────────────────────────────────────────────
        print("1. DEAL AGENT — mandates")

        # The gate FIRST, on the user's real (free) plan. Asserting this before
        # granting Pro is the only way to know the paywall is live: a test that
        # starts by granting itself Pro can never tell you the gate exists.
        st, gated = call("POST", "/purchase/mandates", tok, {
            "name": f"{TAG} gated", "search_query": "x", "max_price": 10})
        chk("deal agent is Pro-gated for a free user (403 PLAN_REQUIRED)",
            st == 403 and "PLAN_REQUIRED" in json.dumps(gated or {}), f"status={st}")

        # Grant Pro for the duration. `subscriptions.plan` + status in
        # (active, trialing) is what app/subscription.py:get_user_plan reads.
        # `provider` is CHECK-constrained to ('stripe','revenuecat'), so the row
        # is tagged via stripe_customer_id instead — a narrower-than-English
        # constraint, exactly the trap the P2P spec records for 'withdrawn'.
        # subscriptions is UNIQUE per user, and this user already has a row, so
        # the grant is an UPDATE whose previous values are captured and restored
        # in the finally block. A test that leaves a real member on a plan they
        # did not buy is worse than no test.
        prev_sub = await conn.fetchrow(
            "SELECT plan, status FROM public.subscriptions WHERE user_id=$1::uuid", user)
        if prev_sub is None:
            await conn.execute(
                """INSERT INTO public.subscriptions
                       (user_id, plan, status, provider, stripe_customer_id)
                   VALUES ($1::uuid, 'pro', 'active', 'stripe', $2)""", user, TAG)
        else:
            await conn.execute(
                "UPDATE public.subscriptions SET plan='pro', status='active' WHERE user_id=$1::uuid",
                user)
        granted_pro = True

        st, free = call("POST", "/purchase/mandates", tok, {
            "name": f"{TAG} free text", "search_query": "charizard", "max_price": 120})
        if not chk("free-text mandate created", st in (200, 201), f"status={st} body={free}"):
            return 1
        chk("a free-text mandate has NO canonical_ref",
            free.get("canonical_ref") in (None, ""), f"ref={free.get('canonical_ref')}")

        st, bad = call("POST", "/purchase/mandates", tok, {
            "name": f"{TAG} bogus key", "search_query": "x", "max_price": 10,
            "canonical_key": "definitely-not-a-real-key-" + uuid.uuid4().hex[:8]})
        chk("unknown canonical_key is rejected at WRITE time (400, not a silent mandate)",
            st == 400 and "UNKNOWN_CANONICAL_KEY" in json.dumps(bad or {}),
            f"status={st} body={bad}")

        real = await conn.fetchrow(
            "SELECT item_key, category FROM public.category_items "
            "WHERE category='pokemon' AND item_key IS NOT NULL LIMIT 1")
        bare_key, cat = real["item_key"], real["category"]

        st, keyed = call("POST", "/purchase/mandates", tok, {
            "name": f"{TAG} keyed", "search_query": "charizard", "max_price": 120,
            "canonical_key": bare_key})
        chk("keyed mandate created from a BARE key", st in (200, 201), f"status={st}")
        keyed_id = (keyed or {}).get("id")
        ref = (keyed or {}).get("canonical_ref") or ""
        stored = await conn.fetchval(
            "SELECT canonical_ref FROM public.purchase_mandates WHERE id=$1::uuid", keyed_id)
        chk("the DB stored a NAMESPACED canonical_ref",
            stored == f"{cat}:{bare_key}", f"sent={bare_key} stored={stored!r}")
        chk("the API RETURNS the canonical_ref it stored",
            ref == (stored or ""), f"stored={stored!r} returned={ref!r}")
        chk("mandate category follows the picked item",
            (keyed or {}).get("category") == cat, f"category={(keyed or {}).get('category')}")

        st, _cleared = call("PATCH", f"/purchase/mandates/{keyed_id}", tok,
                           {"canonical_key": None})
        stored_after = await conn.fetchval(
            "SELECT canonical_ref FROM public.purchase_mandates WHERE id=$1::uuid", keyed_id)
        chk("explicit null CLEARS the key in the DB (omitting would mean unchanged)",
            st == 200 and stored_after is None, f"status={st} stored={stored_after!r}")

        st, listed = call("GET", "/purchase/mandates", tok)
        rows_ = listed if isinstance(listed, list) else (
            (listed or {}).get("mandates") or (listed or {}).get("items") or [])
        names = [m.get("name") for m in rows_]
        chk("both mandates appear in the list", st == 200 and sum(1 for n in names if TAG in (n or "")) >= 2,
            f"status={st} n={len(names)}")

        st, _deals = call("GET", "/purchase/deals?limit=5", tok)
        chk("deals endpoint answers", st == 200, f"status={st}")
        st, stats = call("GET", "/purchase/stats", tok)
        chk("agent stats answer", st == 200, f"status={st} body={stats}")

        # ── 2. SET COMPLETENESS ──────────────────────────────────────────────
        print("\n2. SET COMPLETENESS — the sets → portfolio → set_size chain")

        set_name = f"{TAG} Base Set"
        set_id = await conn.fetchval(
            """INSERT INTO public.sets (id, category_id, name, total_items, metadata)
               VALUES (gen_random_uuid(), 'pokemon', $1, 10, jsonb_build_object('seed', $2::text))
               RETURNING id""",
            set_name, TAG)
        # Own 6 of the 10 — inside the screen's 0.4..0.95 band, so a working
        # chain puts this set ON the screen rather than filtering it away.
        for i in range(6):
            iid = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO public.items (id, user_id, name, category, collection_name,
                                             archived, source)
                   VALUES ($1::uuid, $2::uuid, $3, 'pokemon', $4, FALSE, $5)""",
                iid, user, f"{TAG} card {i}", set_name, "seed:" + TAG)
            made_items.append(iid)

        st, port = call("GET", "/portfolio/items", tok)
        items = (port or {}).get("items", port if isinstance(port, list) else []) or []
        mine = [i for i in items if (i.get("collection_name") or "") == set_name]
        chk("portfolio returns the seeded items", st == 200 and len(mine) == 6,
            f"status={st} n={len(mine)}")
        chk("/portfolio/items carries collection_name (was null → screen empty)",
            all(i.get("collection_name") == set_name for i in mine), "")
        sizes = {i.get("set_size") for i in mine}
        chk("the sets JOIN delivers set_size=10 (the whole bug was this being null)",
            sizes == {10}, f"set_size values={sizes}")

        owned, expected = len(mine), 10
        ratio = owned / expected
        chk("completeness computes to 0.60, inside the screen's 0.4–0.95 band",
            abs(ratio - 0.6) < 1e-9 and 0.4 <= ratio <= 0.95, f"{owned}/{expected} = {ratio:.2f}")

        # The join is lower()-cased on both sides and guarded by a unique index;
        # a duplicate sets row differing only in case would match twice and
        # DOUBLE the owned count with nothing added.
        dup = await conn.fetchval(
            """SELECT count(*) FROM public.sets
               WHERE category_id='pokemon' AND lower(name)=lower($1)""", set_name)
        chk("exactly one sets row matches the join key (case-insensitively)",
            dup == 1, f"rows={dup}")

        st, unknown = call("GET", "/portfolio/items", tok)
        others = [i for i in ((unknown or {}).get("items") or []) if not i.get("collection_name")]
        chk("items with no collection are returned with set_size null, not 0",
            all(i.get("set_size") is None for i in others[:20]),
            f"checked {len(others[:20])} uncollected item(s)")

    finally:
        if granted_pro:
            if prev_sub is None:
                await conn.execute(
                    "DELETE FROM public.subscriptions WHERE user_id=$1::uuid AND stripe_customer_id=$2",
                    user, TAG)
            else:
                await conn.execute(
                    "UPDATE public.subscriptions SET plan=$2, status=$3 WHERE user_id=$1::uuid",
                    user, prev_sub["plan"], prev_sub["status"])
        for iid in made_items:
            await conn.execute("DELETE FROM public.items WHERE id=$1::uuid", iid)
        if set_id:
            await conn.execute("DELETE FROM public.sets WHERE id=$1::uuid", set_id)
        await conn.execute(
            "DELETE FROM public.purchase_mandates WHERE name LIKE $1", TAG + "%")
        left_m = await conn.fetchval(
            "SELECT count(*) FROM public.purchase_mandates WHERE name LIKE $1", TAG + "%")
        left_s = await conn.fetchval(
            "SELECT count(*) FROM public.sets WHERE metadata->>'seed' = $1", TAG)
        left_i = await conn.fetchval(
            "SELECT count(*) FROM public.items WHERE source = $1", "seed:" + TAG)
        now_plan = await conn.fetchval(
            "SELECT plan FROM public.subscriptions WHERE user_id=$1::uuid", user)
        chk("the user's original plan was restored",
            now_plan == (prev_sub["plan"] if prev_sub else None),
            f"plan={now_plan} was={prev_sub['plan'] if prev_sub else None}")
        chk("fixtures cleaned up", (left_m, left_s, left_i) == (0, 0, 0),
            f"mandates={left_m} sets={left_s} items={left_i}")
        await conn.close()

    failed = [r for r in results if not r[0]]
    print(f"\nRESULT: {len(results) - len(failed)} passed, {len(failed)} failed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} | {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
