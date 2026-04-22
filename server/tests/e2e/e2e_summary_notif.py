"""E2E for value_summary + notification endpoints after the lazy-CREATE migration."""
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
    email = "e2e-summary@collectai.app"
    password = "E2ESummary2026!"
    uid = await admin_create_user(email, password)
    jwt = await login(email, password)
    h = {"Authorization": f"Bearer {jwt}"}

    results = []
    async with httpx.AsyncClient(timeout=15) as c:
        for label, path in [
            ("GET /value-summary", "/value-summary"),
            ("GET /notifications", "/notifications"),
            ("GET /notifications/unread-count", "/notifications/unread-count"),
        ]:
            r = await c.get(f"{BASE}{path}", headers=h)
            body = r.text[:160] + ("…" if len(r.text) > 160 else "")
            results.append((label, r.status_code, body))

    await admin_delete_user(uid)

    print("\n=== E2E ===")
    all_ok = True
    for label, code, body in results:
        ok = "✓" if code in (200, 404) else "✗"
        if code not in (200, 404):
            all_ok = False
        print(f"  {ok} [{code}] {label}")
        if code not in (200, 404):
            print(f"         {body}")
    print("\nALL PASS" if all_ok else "\nFAILURES PRESENT")


if __name__ == "__main__":
    asyncio.run(main())
