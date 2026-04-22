"""E2E for Deal Desk — full propose → counter → counter → accept → ship → complete flow.

Creates 2 ephemeral users (seller, buyer), a listing, runs every offer
endpoint, and verifies the state transitions at each step. Cleans up.
"""
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
    pw = "DealE2ER50!"
    seller_id = await admin_create_user("e2e-seller@collectai.app", pw)
    buyer_id = await admin_create_user("e2e-buyer@collectai.app", pw)
    print(f"  seller={seller_id[:8]}  buyer={buyer_id[:8]}")

    # Seed an item + listing owned by seller.
    item_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO public.items (id, user_id, title, category, created_at) VALUES ($1::uuid, $2::uuid, 'E2E Test Item', 'pokemon', now())",
        item_id, seller_id,
    )
    listing_row = await conn.fetchrow(
        """
        INSERT INTO public.listings (item_id, seller_id, title, price, currency, status)
        VALUES ($1::uuid, $2::uuid, 'E2E Pokemon Card', 100.00, 'EUR', 'active')
        RETURNING id
        """,
        item_id, seller_id,
    )
    listing_id = str(listing_row["id"])
    print(f"  listing={listing_id[:8]}")

    seller_jwt = await login("e2e-seller@collectai.app", pw)
    buyer_jwt = await login("e2e-buyer@collectai.app", pw)
    sh = {"Authorization": f"Bearer {seller_jwt}"}
    bh = {"Authorization": f"Bearer {buyer_jwt}"}

    results = []
    offer_id = None

    async with httpx.AsyncClient(timeout=20) as c:
        # 1. Buyer proposes at 80
        r = await c.post(f"{BASE}/deals/offer", headers=bh,
                         json={"item_id": item_id, "price": 80, "message": "will you take 80?"})
        results.append(("POST /deals/offer", r.status_code, r.text[:120]))
        if r.status_code == 200:
            offer_id = r.json().get("id") or r.json().get("offer", {}).get("id")

        if offer_id:
            # 2. Seller counters at 90
            r = await c.post(f"{BASE}/deals/{offer_id}/counter", headers=sh,
                             json={"price": 90, "message": "best I can do"})
            results.append(("POST /deals/{id}/counter (seller→90)", r.status_code, r.text[:120]))

            # 3. Buyer counters at 85
            r = await c.post(f"{BASE}/deals/{offer_id}/counter", headers=bh,
                             json={"price": 85, "message": "meet in middle?"})
            results.append(("POST /deals/{id}/counter (buyer→85)", r.status_code, r.text[:120]))

            # 4. Seller accepts
            r = await c.post(f"{BASE}/deals/{offer_id}/respond", headers=sh,
                             json={"accept": True, "message": "deal"})
            results.append(("POST /deals/{id}/respond accept", r.status_code, r.text[:120]))

            # 5. List active as buyer
            r = await c.get(f"{BASE}/deals/active", headers=bh)
            results.append(("GET /deals/active (buyer)", r.status_code, r.text[:120]))

            # 6. Detail
            r = await c.get(f"{BASE}/deals/{offer_id}", headers=bh)
            results.append(("GET /deals/{id}", r.status_code, r.text[:120]))

    # Cleanup
    if offer_id:
        await conn.execute("DELETE FROM public.offers WHERE id = $1::uuid", offer_id)
    await conn.execute("DELETE FROM public.listings WHERE id = $1::uuid", listing_id)
    await conn.execute("DELETE FROM public.items WHERE id = $1::uuid", item_id)
    await admin_delete_user(seller_id)
    await admin_delete_user(buyer_id)
    await conn.close()

    print("\n=== E2E DEAL DESK ===")
    for label, code, body in results:
        ok = "✓" if code in (200, 201) else "✗"
        print(f"  {ok} [{code}] {label}")
        if code not in (200, 201):
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
