"""E2E test the 4 Pro features with a real JWT minted via Supabase admin.

Flow:
  1. Create an ephemeral test user via admin API (or reuse ci-test).
  2. Seed one items row linked to a known catalog canonical_key (for
     which price_predictions + price_history have data).
  3. Fire curls against each of the 4 endpoints, report status + shape.
  4. Delete the test user at the end (cleanup).
"""

import asyncio, asyncpg, os, httpx, uuid

BASE = "http://localhost:8000"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("EXPO_PUBLIC_SUPABASE_ANON_KEY") or os.environ["SUPABASE_KEY"]


async def admin_create_user(email: str, password: str) -> str:
    """Create a user via service-role auth admin API; returns the user id."""
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={
                "apikey": SERVICE_ROLE,
                "Authorization": f"Bearer {SERVICE_ROLE}",
            },
            json={"email": email, "password": password, "email_confirm": True},
        )
        if r.status_code == 422 and "already been registered" in r.text:
            # fetch existing
            r2 = await c.get(
                f"{SUPABASE_URL}/auth/v1/admin/users?email={email}",
                headers={"apikey": SERVICE_ROLE, "Authorization": f"Bearer {SERVICE_ROLE}"},
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


async def main():
    conn = await asyncpg.connect(os.environ["DB_DSN"], timeout=30)

    # find any item_ref that has recent predictions AND price_history AND hits
    row = await conn.fetchrow("""
        SELECT pp.item_ref
        FROM public.price_predictions pp
        WHERE EXISTS (SELECT 1 FROM public.price_history ph WHERE ph.item_ref = pp.item_ref)
          AND EXISTS (SELECT 1 FROM public.market_hits mh WHERE mh.item_ref = pp.item_ref)
        ORDER BY pp.generated_at DESC
        LIMIT 1
    """)
    if not row:
        row = await conn.fetchrow("SELECT item_ref FROM public.price_predictions ORDER BY generated_at DESC LIMIT 1")
    canonical = row["item_ref"]
    print(f"test canonical_key: {canonical}")

    email = "e2e-test@collectai.app"
    password = "E2ETestR50m!"
    uid = await admin_create_user(email, password)
    print(f"test user id: {uid}")

    # seed items row linked to canonical_key
    item_id = str(uuid.uuid4())
    await conn.execute("""
        INSERT INTO public.items (id, user_id, title, category, canonical_key, created_at)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, now())
        ON CONFLICT (id) DO NOTHING
    """, item_id, uid, "E2E Test Item", canonical.split(":")[0] if ":" in canonical else "misc", canonical)
    print(f"seeded item: {item_id}")

    tok = await login(email, password)
    print(f"token prefix: {tok[:24]}...")

    async with httpx.AsyncClient(base_url=BASE, timeout=30,
                                 headers={"Authorization": f"Bearer {tok}"}) as c:
        # 1. Price Trend
        r = await c.get(f"/predict/trend/{item_id}", params={"days": 90})
        print(f"\n[1] Price Trend {item_id}: status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"    data_points: {len(d.get('data_points', []))}")
            print(f"    current_q50: {d.get('current_q50')}  pct: {d.get('pct_change')}%")
        else:
            print(f"    body: {r.text[:200]}")

        # 2. Dossier
        r = await c.get(f"/dossier/{item_id}")
        print(f"\n[2] Valuation Report: status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"    keys: {list(d.keys())[:8]}")
            val = d.get("valuation") or {}
            ph = d.get("price_history") or []
            mc = d.get("market_comps") or []
            print(f"    valuation.q50={val.get('q50')}  price_history={len(ph)}  market_comps={len(mc)}")
        else:
            print(f"    body: {r.text[:200]}")

        # 3. Provenance
        r = await c.get(f"/provenance/items/{item_id}")
        print(f"\n[3] Item History: status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            events = d.get("events") or []
            print(f"    events: {len(events)}  authenticity_signals: {len(d.get('authenticity_signals') or [])}")
        else:
            print(f"    body: {r.text[:200]}")

        # 4. Marketplace Search
        r = await c.post("/marketplace/search", json={"query": "Black Lotus"})
        print(f"\n[4] Marketplace Search: status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"    keys: {list(d.keys())[:8]}")
            hits = d.get("hits") or d.get("results") or []
            print(f"    hits: {len(hits)}")
        else:
            print(f"    body: {r.text[:200]}")

    # cleanup — leave the test user for future runs (so no churn with Supabase admin API)
    await conn.execute("DELETE FROM public.items WHERE id = $1::uuid", item_id)
    await conn.close()
    print("\ncleanup: test item deleted (user retained for reuse)")


asyncio.run(main())
