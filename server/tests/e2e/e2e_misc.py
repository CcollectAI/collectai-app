"""E2E batch 6 — set progress + sponsor company CRUD."""
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
    pw = "MiscB6_2026!"
    uid = await admin_create_user("e2e-misc@collectai.app", pw)
    jwt = await login("e2e-misc@collectai.app", pw)
    h = {"Authorization": f"Bearer {jwt}"}
    results = []

    # Seed a set + set_item for the progress test
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=30)
    set_row = await conn.fetchrow(
        "INSERT INTO public.sets (category_id, name, external_id, total_items) VALUES ('pokemon','E2E Set','e2e-set',5) RETURNING id"
    )
    set_id = str(set_row["id"])
    set_item_row = await conn.fetchrow(
        "INSERT INTO public.set_items (set_id, name, external_id) VALUES ($1::uuid, 'E2E Item', 'e2e-item-1') RETURNING id",
        set_id,
    )
    set_item_id = str(set_item_row["id"])

    sponsor_company_id = None

    async with httpx.AsyncClient(timeout=20) as c:
        # 1. PUT /sets/{set_id}/progress — add item to user's owned set
        r = await c.put(f"{BASE}/sets/{set_id}/progress", headers=h,
                        json={"item_ids": [set_item_id], "action": "add"})
        results.append(("PUT /sets/{id}/progress add", r.status_code, r.text[:140]))

        # 2. PUT remove
        r = await c.put(f"{BASE}/sets/{set_id}/progress", headers=h,
                        json={"item_ids": [set_item_id], "action": "remove"})
        results.append(("PUT /sets/{id}/progress remove", r.status_code, r.text[:140]))

        # 3. POST /sponsor-companies — create
        r = await c.post(f"{BASE}/sponsor-companies", headers=h, json={
            "name": "E2E Sponsor Co", "contact_email": "sponsor@e2e.collectai.app",
            "website_url": "https://example.com", "description": "audit run",
        })
        results.append(("POST /sponsor-companies", r.status_code, r.text[:140]))
        if r.status_code in (200, 201):
            sponsor_company_id = r.json().get("id")

        # 4. PATCH /sponsor-companies/{id}
        if sponsor_company_id:
            r = await c.patch(f"{BASE}/sponsor-companies/{sponsor_company_id}", headers=h,
                              json={"description": "updated"})
            results.append(("PATCH /sponsor-companies/{id}", r.status_code, r.text[:140]))

            # 5. DELETE /sponsor-companies/{id}
            r = await c.delete(f"{BASE}/sponsor-companies/{sponsor_company_id}", headers=h)
            results.append(("DELETE /sponsor-companies/{id}", r.status_code, r.text[:140]))

    # Cleanup set + set_item
    await conn.execute("DELETE FROM public.set_items WHERE id = $1::uuid", set_item_id)
    await conn.execute("DELETE FROM public.sets WHERE id = $1::uuid", set_id)
    await conn.close()
    await admin_delete_user(uid)

    print("\n=== E2E MISC ===")
    for label, code, body in results:
        ok = "✓" if code < 500 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code >= 400:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
