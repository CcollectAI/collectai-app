"""E2E for the top 5 user-facing write flows that have never been HTTP-tested."""
import asyncio, asyncpg, os, httpx

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
    pw = "WritesE2E2026!"
    uid = await admin_create_user("e2e-writes@collectai.app", pw)
    jwt = await login("e2e-writes@collectai.app", pw)
    h = {"Authorization": f"Bearer {jwt}"}

    results = []
    item_id = None
    watch_id = None

    async with httpx.AsyncClient(timeout=20) as c:
        # 1. POST /items — add item
        r = await c.post(f"{BASE}/items", headers=h,
                         json={"name": "E2E Write Test Card", "category": "pokemon",
                               "collection_name": "test", "estimated_value": 50.0,
                               "notes": "smoke test"})
        results.append(("POST /items (add)", r.status_code, r.text[:140]))
        if r.status_code == 200:
            item_id = r.json().get("id")

        # 2. PATCH /items/{id}/attributes
        if item_id:
            r = await c.patch(f"{BASE}/items/{item_id}/attributes", headers=h,
                              json={"attrs": {"set_name": "Base Set", "rarity": "Holo Rare"}})
            results.append(("PATCH /items/{id}/attributes", r.status_code, r.text[:140]))

        # 3. POST /watchlist/mine — add to watchlist
        r = await c.post(f"{BASE}/watchlist/mine", headers=h,
                         json={"name": "E2E Watchlist Item", "category": "pokemon",
                               "predicted_value": 100.0, "currency": "EUR"})
        results.append(("POST /watchlist/mine", r.status_code, r.text[:140]))
        if r.status_code == 200:
            watch_id = r.json().get("id")

        # 4. POST /quickscan (analyze placeholder request — no real image, expect 422 or 200 depending on validation)
        r = await c.post(f"{BASE}/quickscan", headers=h, json={"image_url": "https://example.com/test.jpg"})
        results.append(("POST /quickscan (no real image)", r.status_code, r.text[:140]))

        # 5. DELETE /items/{id}
        if item_id:
            r = await c.delete(f"{BASE}/items/{item_id}", headers=h)
            results.append(("DELETE /items/{id}", r.status_code, r.text[:140]))

        # Cleanup watchlist
        if watch_id:
            await c.delete(f"{BASE}/watchlist/mine/{watch_id}", headers=h)

    await admin_delete_user(uid)
    await conn.close()

    print("\n=== E2E USER WRITES ===")
    for label, code, body in results:
        # 4xx auth/validation OK; 5xx is a real bug
        ok = "✓" if code < 500 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code >= 400:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
