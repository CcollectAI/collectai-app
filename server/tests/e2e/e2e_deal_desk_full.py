"""Full E2E for Deal Desk including ship + complete."""
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
    pw = "DealE2EFullR50!"
    seller_id = await admin_create_user("e2e-seller-full@collectai.app", pw)
    buyer_id = await admin_create_user("e2e-buyer-full@collectai.app", pw)
    print(f"  seller={seller_id[:8]}  buyer={buyer_id[:8]}")

    item_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO public.items (id, user_id, title, category, created_at) VALUES ($1::uuid, $2::uuid, 'E2E Full Item', 'pokemon', now())",
        item_id, seller_id,
    )
    listing_row = await conn.fetchrow(
        "INSERT INTO public.listings (item_id, seller_id, title, price, currency, status) VALUES ($1::uuid, $2::uuid, 'E2E Full Listing', 100.00, 'EUR', 'active') RETURNING id",
        item_id, seller_id,
    )
    listing_id = str(listing_row["id"])

    seller_jwt = await login("e2e-seller-full@collectai.app", pw)
    buyer_jwt = await login("e2e-buyer-full@collectai.app", pw)
    sh = {"Authorization": f"Bearer {seller_jwt}"}
    bh = {"Authorization": f"Bearer {buyer_jwt}"}

    results = []
    offer_id = None
    async with httpx.AsyncClient(timeout=20) as c:
        # Propose
        r = await c.post(f"{BASE}/deals/offer", headers=bh,
                         json={"item_id": item_id, "price": 80, "message": ""})
        results.append(("propose", r.status_code))
        if r.status_code == 200:
            offer_id = r.json().get("id") or r.json().get("offer", {}).get("id")
        if offer_id:
            # Accept directly (no counter this time)
            r = await c.post(f"{BASE}/deals/{offer_id}/respond", headers=sh,
                             json={"accept": True, "message": "deal"})
            results.append(("accept", r.status_code))
            # Seller ships
            r = await c.post(f"{BASE}/deals/{offer_id}/ship", headers=sh,
                             json={"tracking_info": "TRACK-E2E-1234"})
            results.append(("ship (seller)", r.status_code))
            # Buyer completes + rates
            r = await c.post(f"{BASE}/deals/{offer_id}/complete", headers=bh,
                             json={"stars": 5, "comment": "great seller"})
            results.append(("complete + rate (buyer)", r.status_code))
            # Confirm final state
            r = await c.get(f"{BASE}/deals/{offer_id}", headers=bh)
            results.append(("detail", r.status_code))

    if offer_id:
        await conn.execute("DELETE FROM public.deal_ratings WHERE offer_id = $1::uuid", offer_id)
        await conn.execute("DELETE FROM public.offer_events WHERE offer_id = $1::uuid", offer_id)
        await conn.execute("DELETE FROM public.offers WHERE id = $1::uuid", offer_id)
    await conn.execute("DELETE FROM public.listings WHERE id = $1::uuid", listing_id)
    await conn.execute("DELETE FROM public.items WHERE id = $1::uuid", item_id)
    await admin_delete_user(seller_id); await admin_delete_user(buyer_id)
    await conn.close()

    print("\n=== E2E DEAL DESK FULL ===")
    for label, code in results:
        ok = "✓" if code == 200 else "✗"
        print(f"  {ok} [{code}] {label}")

if __name__ == "__main__":
    asyncio.run(main())
