"""E2E test for chat_router.py — full DM flow with request-gated threads.

Flow (Instagram/WhatsApp-style):
  1. Admin creates 2 ephemeral users (Alice, Bob) via Supabase admin API.
  2. Directly insert a dm_threads row with status='accepted' (simulates
     Bob having accepted Alice's request). In production this happens via
     a separate DM-request endpoint, not the chat router.
  3. Login as Alice → POST /chat/threads/{id}/messages
  4. Login as Bob  → GET /chat/threads (see thread)
  5. Bob → GET /chat/threads/{id}/messages (see Alice's msg)
  6. Bob → PATCH /chat/threads/{id}/read (mark read)
  7. Bob → GET /chat/unread-count (should be 0)
  8. Alice → PATCH /chat/messages/{msg_id} (edit within 15min)
  9. Alice → DELETE /chat/messages/{msg_id} (soft delete)
  10. Cleanup ephemeral users + thread.
"""
import asyncio, asyncpg, os, httpx, uuid, json

BASE = "http://localhost:8000"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or os.environ["SUPABASE_KEY"]


async def admin_create_user(email, password):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
            json={"email": email, "password": password, "email_confirm": True},
        )
        if r.status_code == 422 and "already" in r.text.lower():
            r2 = await c.get(
                f"{SUPABASE_URL}/auth/v1/admin/users?email={email}",
                headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
            )
            r2.raise_for_status()
            return r2.json()["users"][0]["id"]
        r.raise_for_status()
        return r.json()["id"]


async def login(email, password):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON},
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def admin_delete_user(uid):
    async with httpx.AsyncClient(timeout=10) as c:
        await c.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
        )


def shorten(obj, n=180):
    s = json.dumps(obj, default=str) if not isinstance(obj, str) else obj
    return s[:n] + ("…" if len(s) > n else "")


async def main():
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ["DB_DSN"]
    conn = await asyncpg.connect(dsn, timeout=30)

    alice_email = "e2e-alice@collectai.app"
    bob_email = "e2e-bob@collectai.app"
    password = "E2ETestChat2026!"

    alice_id = await admin_create_user(alice_email, password)
    bob_id = await admin_create_user(bob_email, password)
    print(f"  users: alice={alice_id[:8]}… bob={bob_id[:8]}…")

    # Simulate Bob accepting Alice's DM request.
    thread_row = await conn.fetchrow(
        """
        INSERT INTO public.dm_threads (requester_id, responder_id, status)
        VALUES ($1, $2, 'accepted')
        RETURNING id
        """,
        alice_id, bob_id,
    )
    thread_id = str(thread_row["id"])
    print(f"  thread: {thread_id[:8]}…  status=accepted")

    alice_jwt = await login(alice_email, password)
    bob_jwt = await login(bob_email, password)

    ah = {"Authorization": f"Bearer {alice_jwt}"}
    bh = {"Authorization": f"Bearer {bob_jwt}"}

    results = []

    async with httpx.AsyncClient(timeout=15) as c:
        # 1. Alice sends message
        r = await c.post(
            f"{BASE}/chat/threads/{thread_id}/messages",
            headers=ah, json={"content": "Hey Bob — first e2e test msg!"},
        )
        results.append(("POST /chat/threads/.../messages (Alice)", r.status_code, shorten(r.text)))
        msg_id = None
        if r.status_code == 200:
            msg_id = r.json()["message"]["id"]

        # 2. Bob lists threads
        r = await c.get(f"{BASE}/chat/threads", headers=bh)
        results.append(("GET /chat/threads (Bob)", r.status_code, shorten(r.text)))

        # 3. Bob gets messages in the thread
        r = await c.get(f"{BASE}/chat/threads/{thread_id}/messages", headers=bh)
        results.append(("GET /chat/threads/.../messages (Bob)", r.status_code, shorten(r.text)))

        # 4. Bob marks thread read
        r = await c.patch(f"{BASE}/chat/threads/{thread_id}/read", headers=bh)
        results.append(("PATCH /chat/threads/.../read (Bob)", r.status_code, shorten(r.text)))

        # 5. Bob unread count
        r = await c.get(f"{BASE}/chat/unread-count", headers=bh)
        results.append(("GET /chat/unread-count (Bob)", r.status_code, shorten(r.text)))

        # 6. Alice edits her message
        if msg_id:
            r = await c.patch(
                f"{BASE}/chat/messages/{msg_id}",
                headers=ah, json={"content": "Hey Bob — edited!"},
            )
            results.append(("PATCH /chat/messages/{id} (Alice edit)", r.status_code, shorten(r.text)))

            # 7. Alice deletes her message
            r = await c.delete(f"{BASE}/chat/messages/{msg_id}", headers=ah)
            results.append(("DELETE /chat/messages/{id} (Alice delete)", r.status_code, shorten(r.text)))

    # Cleanup
    await conn.execute("DELETE FROM public.dm_threads WHERE id = $1::uuid", thread_id)
    await admin_delete_user(alice_id)
    await admin_delete_user(bob_id)
    await conn.close()

    print("\n=== E2E RESULTS ===")
    all_ok = True
    for label, code, body in results:
        ok = "✓" if code == 200 else "✗"
        if code != 200:
            all_ok = False
        print(f"  {ok} [{code}] {label}")
        if code != 200:
            print(f"         {body}")
    print("\nALL PASS" if all_ok else "\nFAILURES PRESENT")

if __name__ == "__main__":
    asyncio.run(main())
