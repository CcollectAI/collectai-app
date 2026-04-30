"""End-to-end verify the entire DM/chat flow.

Two test users (ci-test + a synthetic peer). The flow:
  1. ci-test sends a DM request to peer (rpc_request_dm_v1)
  2. peer accepts it (rpc_decide_dm_request_v1) — this creates the
     chat_threads_v1 row + 2 chat_thread_members_v1 rows
  3. ci-test sends a message (rpc_send_message_v1)
  4. peer reads inbox (v_chat_inbox_v1) — sees thread with unread=1
  5. peer marks read (rpc_mark_thread_read_v1) — chat_thread_reads_v1
  6. ci-test edits the message (PATCH /chat/messages/{id})
  7. ci-test deletes the message (DELETE /chat/messages/{id})
  8. /chat/unread-count for both
  9. cleanup
"""
import os, json, urllib.request, urllib.error, time, jwt, asyncio, asyncpg

CI_TEST = "20503ad2-c62d-4700-810b-36da247bbf28"
# Peer user — must be created via /tmp/create_peer.py first; passed via env.
PEER = os.environ.get("PEER_USER_ID")
if not PEER:
    raise SystemExit("PEER_USER_ID env not set — run scripts/create_peer.py first")

secret = os.environ["SUPABASE_JWT_SECRET"]
issuer = os.environ.get("SUPABASE_JWT_ISSUER", "")

def mint(sub: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "aud": "authenticated", "role": "authenticated",
                       "iat": now, "exp": now + 3600, "iss": issuer},
                      secret, algorithm="HS256")

CI_TOKEN = mint(CI_TEST)
PEER_TOKEN = mint(PEER)

EC2 = "http://localhost:8000"
SUPA = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
ANON = os.environ["SUPABASE_KEY"]

def hit_ec2(token: str, method: str, path: str, body=None):
    h = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if body is not None: h["Content-Type"] = "application/json"
    data = json.dumps(body, default=str).encode() if body is not None else None
    req = urllib.request.Request(EC2 + path, method=method, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def supa_rpc(token: str, name: str, params):
    url = f"{SUPA}/rpc/{name}"
    body = json.dumps(params, default=str).encode()
    req = urllib.request.Request(url, method="POST", data=body,
        headers={"apikey": ANON, "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def supa_select(token: str, table: str, query: str = ""):
    url = f"{SUPA}/{table}{('?' + query) if query else ''}"
    req = urllib.request.Request(url, method="GET",
        headers={"apikey": ANON, "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

PACE = 2.0
res = []
def mark(label, ok, detail=""):
    res.append((label, ok, detail))
    print(f"  {'✓' if ok else '✗'} {label:50s}  {detail[:120]}", flush=True)

async def main():
    conn = await asyncpg.connect(os.environ["DB_DSN_DIRECT"])
    await conn.execute("SET statement_timeout = 0")
    print(f"CI={CI_TEST}  PEER={PEER}", flush=True)
    print("Cooldown 30s…", flush=True); time.sleep(30)

    # Step 1: ci-test → peer DM request
    time.sleep(PACE)
    code, body = supa_rpc(CI_TOKEN, "rpc_request_dm_v1",
                          {"p_target_user_id": PEER, "p_context": {"message": "E2E DM"}})
    request_id = (json.loads(body) or {}).get("request_id") if code == 200 else None
    row = await conn.fetchrow(
        "SELECT id, status, requester_id, target_user_id, context FROM chat_dm_requests_v1 WHERE id = $1::uuid",
        request_id,
    ) if request_id else None
    mark("requestDm → row in chat_dm_requests_v1",
         bool(row) and row["status"] == "pending" and str(row["requester_id"]) == CI_TEST,
         f"id={request_id} status={row['status'] if row else None}")

    # Step 2: peer accepts → creates thread + 2 member rows
    time.sleep(PACE)
    if request_id:
        code, body = supa_rpc(PEER_TOKEN, "rpc_decide_dm_request_v1",
                              {"p_request_id": request_id, "p_approve": True})
        out = json.loads(body) if code == 200 else {}
        thread_id = out.get("thread_id")
        member_count = await conn.fetchval(
            "SELECT count(*) FROM chat_thread_members_v1 WHERE thread_id = $1::uuid",
            thread_id,
        ) if thread_id else 0
        mark("decideDmRequest accept → thread + 2 members",
             code == 200 and thread_id and member_count == 2,
             f"thread={thread_id} members={member_count}")
    else:
        thread_id = None

    # Step 3: ci-test sends a message
    time.sleep(PACE)
    msg_id = None
    if thread_id:
        code, body = supa_rpc(CI_TOKEN, "rpc_send_message_v1",
                              {"p_thread_id": thread_id, "p_user_id": CI_TEST, "p_body": "Hello peer"})
        # rpc_send_message_v1 returns the chat_messages_v1 row
        out = json.loads(body) if code == 200 else {}
        msg_id = (out.get("id") if isinstance(out, dict) else None)
        row = await conn.fetchrow(
            "SELECT id, body, user_id FROM chat_messages_v1 WHERE id = $1::uuid", msg_id,
        ) if msg_id else None
        mark("sendMessage → row in chat_messages_v1",
             bool(row) and row["body"] == "Hello peer",
             f"msg_id={msg_id} body={row['body'] if row else None!r}")

    # Step 4: peer reads inbox (v_chat_inbox_v1)
    time.sleep(PACE)
    code, data = supa_select(PEER_TOKEN, "v_chat_inbox_v1", "select=thread_id,unread_count,last_message_body&limit=5")
    inbox_threads = data if isinstance(data, list) else []
    own_thread = next((t for t in inbox_threads if t.get("thread_id") == thread_id), None)
    mark("peer inbox sees thread with unread=1",
         bool(own_thread) and own_thread.get("unread_count", 0) >= 1,
         f"unread={own_thread.get('unread_count') if own_thread else None}")

    # Step 5: peer marks read
    time.sleep(PACE)
    if thread_id:
        code, body = supa_rpc(PEER_TOKEN, "rpc_mark_thread_read_v1", {"p_thread_id": thread_id})
        # chat_thread_reads_v1 has thread_id + user_id + last_read_at
        row = await conn.fetchrow(
            "SELECT last_read_at FROM chat_thread_reads_v1 WHERE thread_id = $1::uuid AND user_id = $2::uuid",
            thread_id, PEER,
        )
        mark("markThreadRead → chat_thread_reads_v1", code in (200, 204) and row and row["last_read_at"],
             f"last_read_at={row['last_read_at'] if row else None}")

    # Step 6: ci-test edits the message via PATCH /chat/messages/{id}
    time.sleep(PACE)
    if msg_id:
        code, body = hit_ec2(CI_TOKEN, "PATCH", f"/chat/messages/{msg_id}", {"content": "Hello peer (edited)"})
        edited = await conn.fetchval("SELECT body FROM chat_messages_v1 WHERE id = $1::uuid", msg_id)
        mark("editChatMessage PATCH → body updated",
             code in (200, 204) and edited == "Hello peer (edited)",
             f"HTTP {code} body={edited!r}")

    # Step 7: ci-test deletes
    time.sleep(PACE)
    if msg_id:
        code, _ = hit_ec2(CI_TOKEN, "DELETE", f"/chat/messages/{msg_id}")
        # Real schema: chat_messages_v1 has deleted_at — soft delete
        deleted_at = await conn.fetchval(
            "SELECT deleted_at FROM chat_messages_v1 WHERE id = $1::uuid", msg_id,
        )
        mark("deleteChatMessage → deleted_at set",
             code in (200, 204) and deleted_at,
             f"HTTP {code} deleted_at={deleted_at}")

    # Step 8: unread count for both
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", "/chat/unread-count")
    mark("ci-test /chat/unread-count", code == 200, body[:80])
    time.sleep(PACE)
    code, body = hit_ec2(PEER_TOKEN, "GET", "/chat/unread-count")
    mark("peer /chat/unread-count", code == 200, body[:80])

    # Step 9: typing
    time.sleep(PACE)
    if thread_id:
        code, _ = supa_rpc(CI_TOKEN, "rpc_set_typing_v1", {"p_thread_id": thread_id})
        row = await conn.fetchrow(
            "SELECT user_id, is_typing FROM chat_typing_v1 WHERE thread_id = $1::uuid AND user_id = $2::uuid",
            thread_id, CI_TEST,
        )
        mark("setTyping → chat_typing_v1.is_typing", code == 200 and row and row["is_typing"],
             f"is_typing={row['is_typing'] if row else None}")
        time.sleep(PACE)
        code, _ = supa_rpc(CI_TOKEN, "rpc_clear_typing_v1", {"p_thread_id": thread_id})
        row = await conn.fetchrow(
            "SELECT is_typing FROM chat_typing_v1 WHERE thread_id = $1::uuid AND user_id = $2::uuid",
            thread_id, CI_TEST,
        )
        # rpc_clear_typing_v1 DELETEs the row + RETURNS void → PostgREST 204.
        # rpc_get_typing_v1 only returns rows where is_typing=true, so a missing
        # row reads as "not typing" downstream — same UX, simpler write path.
        mark("clearTyping → typing row gone",
             code in (200, 204) and row is None,
             f"HTTP {code} row={row}")

    # Step 10: getDmStatus
    time.sleep(PACE)
    code, body = supa_select(CI_TOKEN, "chat_dm_requests_v1",
                             f"select=status,requester_id,target_user_id,thread_id"
                             f"&or=(and(requester_id.eq.{CI_TEST},target_user_id.eq.{PEER}),"
                             f"and(requester_id.eq.{PEER},target_user_id.eq.{CI_TEST}))"
                             f"&order=created_at.desc&limit=1")
    rows = body if isinstance(body, list) else []
    has_status = bool(rows) and rows[0].get("status") in ("approved", "denied", "pending")
    mark("getDmStatus query (chat_dm_requests_v1)", code == 200 and has_status,
         f"status={rows[0].get('status') if rows else None}")

    # Cleanup
    print("\n=== CLEANUP ===", flush=True)
    if thread_id:
        await conn.execute("DELETE FROM chat_typing_v1 WHERE thread_id = $1::uuid", thread_id)
        await conn.execute("DELETE FROM chat_thread_reads_v1 WHERE thread_id = $1::uuid", thread_id)
        await conn.execute("DELETE FROM chat_messages_v1 WHERE thread_id = $1::uuid", thread_id)
        await conn.execute("DELETE FROM chat_thread_members_v1 WHERE thread_id = $1::uuid", thread_id)
        await conn.execute("DELETE FROM chat_threads_v1 WHERE id = $1::uuid", thread_id)
    if request_id:
        await conn.execute("DELETE FROM chat_dm_requests_v1 WHERE id = $1::uuid", request_id)
    print("  cleaned up")
    await conn.close()

    ok = sum(1 for _, success, _ in res if success)
    print(f"\n=== SUMMARY ===")
    print(f"  PASS: {ok}/{len(res)}    FAIL: {len(res) - ok}")
    if ok != len(res):
        print(f"\n  FAILS:")
        for label, success, detail in res:
            if not success:
                print(f"    ✗ {label}  — {detail[:160]}")

asyncio.run(main())
