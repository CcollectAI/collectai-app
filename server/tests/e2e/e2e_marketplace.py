"""E2E batch 5 — marketplace search + listings + fees."""
import asyncio, asyncpg, os, httpx, uuid
BASE = "http://localhost:8000"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or os.environ["SUPABASE_KEY"]


async def admin_create_user(email, password):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
            json={"email": email, "password": password, "email_confirm": True})
        if r.status_code == 422 and "already" in r.text.lower():
            r2 = await c.get(f"{SUPABASE_URL}/auth/v1/admin/users?email={email}",
                headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"})
            return r2.json()["users"][0]["id"]
        r.raise_for_status()
        return r.json()["id"]


async def login(email, password):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON}, json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


async def admin_delete_user(uid):
    async with httpx.AsyncClient(timeout=10) as c:
        await c.delete(f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"})


async def main():
    pw = "MktB5_2026!"
    uid = await admin_create_user("e2e-mkt@collectai.app", pw)
    jwt = await login("e2e-mkt@collectai.app", pw)
    h = {"Authorization": f"Bearer {jwt}"}
    results = []

    # Seed an item to use for listing creation
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=90)
    item_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO public.items (id, user_id, title, category, created_at) VALUES ($1::uuid, $2::uuid, 'Mkt E2E Item', 'pokemon', now())",
        item_id, uid,
    )
    listing_id = None

    async with httpx.AsyncClient(timeout=90) as c:
        # 1. POST /marketplace/search — aggregate sold-comp search (live, slow ~30s)
        r = await c.post(f"{BASE}/marketplace/search", headers=h,
                         json={"query": "Charizard Base Set", "category": "pokemon", "limit": 5})
        results.append(("POST /marketplace/search", r.status_code, r.text[:140]))

        # 2. POST /marketplace/listings/fees/calculate — pure-function, no Stripe
        r = await c.post(f"{BASE}/marketplace/listings/fees/calculate", headers=h,
                         json={"marketplace_id": "ebay", "price": 50.0, "shipping_cost": 5.0})
        results.append(("POST /marketplace/listings/fees/calculate", r.status_code, r.text[:140]))

        # 3. POST /marketplace/listings — create listing
        r = await c.post(f"{BASE}/marketplace/listings", headers=h, json={
            "item_id": item_id, "marketplace_id": "ebay",
            "listing_title": "E2E Listing", "price": 50.0, "currency": "EUR",
        })
        results.append(("POST /marketplace/listings", r.status_code, r.text[:140]))
        if r.status_code in (200, 201):
            listing_id = r.json().get("id")

        # 4. PATCH /marketplace/listings/{id}
        if listing_id:
            r = await c.patch(f"{BASE}/marketplace/listings/{listing_id}", headers=h,
                              json={"price": 55.0})
            results.append(("PATCH /marketplace/listings/{id}", r.status_code, r.text[:140]))

            # 5. DELETE /marketplace/listings/{id}
            r = await c.delete(f"{BASE}/marketplace/listings/{listing_id}", headers=h)
            results.append(("DELETE /marketplace/listings/{id}", r.status_code, r.text[:140]))

    if listing_id:
        await conn.execute("DELETE FROM public.listings WHERE id = $1::uuid", listing_id)
    await conn.execute("DELETE FROM public.items WHERE id = $1::uuid", item_id)
    await conn.close()
    await admin_delete_user(uid)

    print("\n=== E2E MARKETPLACE ===")
    for label, code, body in results:
        ok = "✓" if code < 500 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code >= 400:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
