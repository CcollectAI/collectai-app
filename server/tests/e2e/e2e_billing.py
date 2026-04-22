"""Quick E2E for billing endpoints — verifies auth + validation, doesn't actually charge."""
import asyncio, os, httpx
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
    pw = "BillE2E2026!"
    uid = await admin_create_user("e2e-billing@collectai.app", pw)
    jwt = await login("e2e-billing@collectai.app", pw)
    h = {"Authorization": f"Bearer {jwt}"}
    results = []

    async with httpx.AsyncClient(timeout=20) as c:
        # 1. POST /billing/checkout-session — pro/monthly
        r = await c.post(f"{BASE}/billing/checkout-session", headers=h,
                         json={"plan": "pro", "interval": "monthly"})
        results.append(("POST /billing/checkout-session pro/monthly", r.status_code, r.text[:160]))

        # 2. POST /billing/portal-session — Stripe customer portal (only works if user has a Stripe customer)
        r = await c.post(f"{BASE}/billing/portal-session", headers=h, json={})
        results.append(("POST /billing/portal-session", r.status_code, r.text[:160]))

        # 3. Validation: bad plan
        r = await c.post(f"{BASE}/billing/checkout-session", headers=h,
                         json={"plan": "godmode", "interval": "monthly"})
        results.append(("POST /billing/checkout-session bad-plan (expect 400)", r.status_code, r.text[:120]))

    await admin_delete_user(uid)

    print("\n=== E2E BILLING ===")
    for label, code, body in results:
        ok = "✓" if code < 500 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code >= 400:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
