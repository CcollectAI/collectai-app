"""E2E batch 4 — events RSVP + category follow + create event + social block."""
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
    pw = "EventsB4_2026!"
    me_id = await admin_create_user("e2e-events@collectai.app", pw)
    other_id = await admin_create_user("e2e-events-other@collectai.app", pw)
    jwt = await login("e2e-events@collectai.app", pw)
    h = {"Authorization": f"Bearer {jwt}"}
    results = []
    event_id = None

    async with httpx.AsyncClient(timeout=20) as c:
        # 1. POST /events — create event
        r = await c.post(f"{BASE}/events", headers=h, json={
            "title": "E2E Test Convention",
            "kind": "convention",
            "category_id": "pokemon",
            "date": "2026-12-01",
            "location": "Test Hall, Amsterdam",
        })
        results.append(("POST /events (create)", r.status_code, r.text[:140]))
        if r.status_code in (200, 201):
            event_id = r.json().get("id")

        # 2. POST /events/{id}/rsvp
        if event_id:
            r = await c.post(f"{BASE}/events/{event_id}/rsvp", headers=h, json={"status": "going"})
            results.append(("POST /events/{id}/rsvp", r.status_code, r.text[:140]))

        # 3. POST /events/categories/{cat}/follow
        r = await c.post(f"{BASE}/events/categories/pokemon/follow", headers=h)
        results.append(("POST /events/categories/{cat}/follow", r.status_code, r.text[:140]))

        # 4. DELETE /events/categories/{cat}/follow (unfollow)
        r = await c.delete(f"{BASE}/events/categories/pokemon/follow", headers=h)
        results.append(("DELETE /events/categories/{cat}/follow", r.status_code, r.text[:140]))

        # 5. POST /social/block/{user_id}
        r = await c.post(f"{BASE}/social/block/{other_id}", headers=h)
        results.append(("POST /social/block/{user_id}", r.status_code, r.text[:140]))

        # 6. DELETE /social/block/{user_id} (unblock)
        r = await c.delete(f"{BASE}/social/block/{other_id}", headers=h)
        results.append(("DELETE /social/block/{user_id}", r.status_code, r.text[:140]))

    # Cleanup event
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=30)
    if event_id:
        await conn.execute("DELETE FROM public.events WHERE id = $1::uuid", event_id)
    await conn.close()
    await admin_delete_user(me_id); await admin_delete_user(other_id)

    print("\n=== E2E EVENTS + SOCIAL ===")
    for label, code, body in results:
        ok = "✓" if code < 500 else "✗"
        print(f"  {ok} [{code}] {label}")
        if code >= 400:
            print(f"         {body}")

if __name__ == "__main__":
    asyncio.run(main())
