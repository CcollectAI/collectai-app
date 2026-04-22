"""E2E for the 4 (now 5) untested deal_desk edges."""
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
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=30)
    pw = "DealEdgeR50!"
    seller_id = await admin_create_user("e2e-edge-s@collectai.app", pw)
    buyer_id = await admin_create_user("e2e-edge-b@collectai.app", pw)

    item_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO public.items (id, user_id, title, category, created_at) VALUES ($1::uuid, $2::uuid, 'Edge Item', 'pokemon', now())",
        item_id, seller_id,
    )
    listing_row = await conn.fetchrow(
        "INSERT INTO public.listings (item_id, seller_id, title, price, currency, status) VALUES ($1::uuid, $2::uuid, 'Edge', 100, 'EUR', 'active') RETURNING id",
        item_id, seller_id,
    )
    listing_id = str(listing_row["id"])

    seller_jwt = await login("e2e-edge-s@collectai.app", pw)
    buyer_jwt  = await login("e2e-edge-b@collectai.app", pw)
    sh = {"Authorization": f"Bearer {seller_jwt}"}
    bh = {"Authorization": f"Bearer {buyer_jwt}"}

    results = []
    offer_id = None
    async with httpx.AsyncClient(timeout=20) as c:
        # Need an offer to test offer-scoped endpoints
        r = await c.post(f"{BASE}/deals/offer", headers=bh,
                         json={"item_id": item_id, "price": 80, "message": ""})
        if r.status_code == 200:
            offer_id = r.json().get("id")

        # 1. GET /deals/history (no completed yet — should return 200 with empty)
        r = await c.get(f"{BASE}/deals/history", headers=bh)
        results.append(("GET /deals/history", r.status_code, r.text[:120]))

        # 2. GET /deals/{id}/evidence (no evidence yet — should return 200 with null)
        if offer_id:
            r = await c.get(f"{BASE}/deals/{offer_id}/evidence", headers=bh)
            results.append(("GET /deals/{id}/evidence", r.status_code, r.text[:120]))

        # 3. GET /deals/reputation/{user_id}
        r = await c.get(f"{BASE}/deals/reputation/{seller_id}", headers=bh)
        results.append(("GET /deals/reputation/{seller}", r.status_code, r.text[:120]))

        # 4. GET /deals/{id}/risk-flags (bonus — known-suspicious)
        if offer_id:
            r = await c.get(f"{BASE}/deals/{offer_id}/risk-flags", headers=bh)
            results.append(("GET /deals/{id}/risk-flags", r.status_code, r.text[:120]))

        # 5. PUT /items/{item_id}/for-sale (seller toggling their own item)
        r = await c.put(f"{BASE}/items/{item_id}/for-sale", headers=sh,
                        json={"for_sale": True, "asking_price": 95, "currency": "EUR"})
        results.append(("PUT /items/{id}/for-sale", r.status_code, r.text[:120]))

    if offer_id:
        await conn.execute("DELETE FROM public.offer_events WHERE offer_id = $1::uuid", offer_id)
        await conn.execute("DELETE FROM public.offers WHERE id = $1::uuid", offer_id)
    await conn.execute("DELETE FROM public.listings WHERE id = $1::uuid", listing_id)
    await conn.execute("DELETE FROM public.items WHERE id = $1::uuid", item_id)
    await admin_delete_user(seller_id); await admin_delete_user(buyer_id)
    await conn.close()

    print("\n=== E2E DEAL DESK EDGES ===")
    for label, code, body in results:
        ok = "✓" if code == 200 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code != 200:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
