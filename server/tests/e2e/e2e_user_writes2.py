"""E2E batch 2 — beta signup (public) + settings + notifications + photos."""
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
    pw = "WritesB2_2026!"
    uid = await admin_create_user("e2e-writes2@collectai.app", pw)
    jwt = await login("e2e-writes2@collectai.app", pw)
    h = {"Authorization": f"Bearer {jwt}"}
    results = []

    async with httpx.AsyncClient(timeout=20) as c:
        # 1. POST /api/beta-signup (public, no auth)
        import time
        unique_email = f"beta-{int(time.time())}@example.com"
        r = await c.post(f"{BASE}/api/beta-signup", json={"email": unique_email, "referral_source": "e2e-test"})
        results.append(("POST /api/beta-signup", r.status_code, r.text[:140]))

        # 2. PATCH /settings/alert-preferences
        r = await c.patch(f"{BASE}/settings/alert-preferences", headers=h,
                          json={"price_drop_enabled": True, "price_drop_threshold": 15})
        results.append(("PATCH /settings/alert-preferences", r.status_code, r.text[:140]))

        # 3. POST /notifications/register (push token)
        r = await c.post(f"{BASE}/notifications/register", headers=h,
                         json={"token": "ExpoPushToken[E2E-FAKE-TOKEN-1234]", "platform": "ios"})
        results.append(("POST /notifications/register", r.status_code, r.text[:140]))

        # 4. PUT /notifications/preferences
        r = await c.put(f"{BASE}/notifications/preferences", headers=h,
                        json={"price_alerts": True, "deal_alerts": False})
        results.append(("PUT /notifications/preferences", r.status_code, r.text[:140]))

        # 5. POST /notifications/mark-all-read
        r = await c.post(f"{BASE}/notifications/mark-all-read", headers=h)
        results.append(("POST /notifications/mark-all-read", r.status_code, r.text[:140]))

        # 6. POST /photos/presign-upload (gets a signed URL — no actual S3 upload)
        r = await c.post(f"{BASE}/photos/presign-upload", headers=h,
                         json={"item_id": "00000000-0000-0000-0000-000000000000", "ext": "jpg"})
        results.append(("POST /photos/presign-upload", r.status_code, r.text[:140]))

    await admin_delete_user(uid)

    print("\n=== E2E USER WRITES BATCH 2 ===")
    for label, code, body in results:
        ok = "✓" if code < 500 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code >= 400:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
