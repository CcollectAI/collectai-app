#!/usr/bin/env python3
"""
Authenticated end-to-end flow smoke test.

WHY THIS EXISTS: CI runs lint + types + GET smoke tests, but nothing logged in
as a real user and exercised an authenticated WRITE flow. So chat / create-event
/ follow / watchlist broke silently and only surfaced when tapped on a build
(and the device itself was blocked by an unrelated auth bug). This logs in as
two throwaway users via the Supabase service key and runs the real flows against
the deployed backend, asserting outcomes — catching FE/BE contract drift, RLS
returns-[], RPC param drift, and 404/422s before they reach a build.

Mirrors the REAL client paths:
  - chat inbox  -> supabase.from('v_chat_inbox_v1') (PostgREST, RLS auth.uid())
  - chat send   -> EC2 POST /chat/threads/{id}/messages  body {"content": ...}
  - DM request/accept -> Supabase RPC rpc_request_dm_v1 / rpc_decide_dm_request_v1
  - create event -> EC2 POST /events
  - follow / watchlist -> EC2 routes

Run on EC2 (env from /opt/collectors/.env):
    set -a; . /opt/collectors/.env; set +a
    /opt/collectors/.venv/bin/python server/scripts/e2e_authed_flows.py
Exits non-zero if any step fails. Deletes the throwaway users on the way out.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import jwt

API_BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8000")
SU = os.environ["SUPABASE_URL"]
ANON = os.environ["EXPO_PUBLIC_SUPABASE_ANON_KEY"]
SRK = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
SEC = os.environ["SUPABASE_JWT_SECRET"]
ISS = os.environ.get("SUPABASE_JWT_ISSUER")

results: list[tuple[str, bool, str]] = []


def _http(url, method, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _admin_create(email):
    sc, b = _http(
        f"{SU}/auth/v1/admin/users", "POST",
        {"apikey": SRK, "Authorization": f"Bearer {SRK}"},
        {"email": email, "password": "E2eProbe123!", "email_confirm": True},
    )
    return json.loads(b).get("id") if sc < 300 else None


def _admin_delete(uid):
    if uid:
        _http(f"{SU}/auth/v1/admin/users/{uid}", "DELETE",
              {"apikey": SRK, "Authorization": f"Bearer {SRK}"})


def _mint(uid):
    c = {"sub": uid, "aud": "authenticated", "role": "authenticated",
         "exp": int(time.time()) + 3600, "iat": int(time.time())}
    if ISS:
        c["iss"] = ISS
    return jwt.encode(c, SEC, algorithm="HS256")


def _rpc(fn, body, tok):
    return _http(f"{SU}/rest/v1/rpc/{fn}", "POST",
                 {"apikey": ANON, "Authorization": f"Bearer {tok}"}, body)


def _rest_get(path, tok):
    return _http(f"{SU}/rest/v1/{path}", "GET",
                 {"apikey": ANON, "Authorization": f"Bearer {tok}"})


def _ec2(method, path, tok, body=None):
    return _http(API_BASE + path, method, {"Authorization": f"Bearer {tok}"}, body)


def check(name, cond, detail=""):
    results.append((name, bool(cond), str(detail)[:160]))


def main():
    ts = int(time.time())
    a = _admin_create(f"e2e_a_{ts}@example.com")
    b = _admin_create(f"e2e_b_{ts}@example.com")
    if not a or not b:
        print("FATAL: could not create test users")
        return 2
    ta, tb = _mint(a), _mint(b)
    try:
        # ---- chat ----
        sc, body = _rpc("rpc_request_dm_v1", {"p_target_user_id": b, "p_context": {}}, ta)
        rid = (json.loads(body).get("request_id") if sc == 200 else None)
        check("chat.request_dm", sc == 200 and rid, f"{sc} {body}")
        time.sleep(1)
        sc, body = _rpc("rpc_decide_dm_request_v1", {"p_request_id": rid, "p_approve": True}, tb)
        thr = (json.loads(body).get("thread_id") if sc == 200 else None)
        check("chat.accept", sc == 200 and thr, f"{sc} {body}")
        time.sleep(1)
        # Inbox via the REAL FE path (PostgREST view, RLS auth.uid()).
        sc, body = _rest_get("v_chat_inbox_v1?select=thread_id", ta)
        check("chat.inbox_shows_thread", sc == 200 and thr and thr in body, f"{sc} {body}")
        sc, body = _ec2("POST", f"/chat/threads/{thr}/messages", ta, {"content": "e2e hello"})
        check("chat.send", sc == 200, f"{sc} {body}")
        time.sleep(1)
        sc, body = _ec2("GET", f"/chat/threads/{thr}/messages", tb)
        check("chat.recipient_reads", sc == 200 and "e2e hello" in body, f"{sc}")

        # ---- create event ----
        fut = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 7 * 86400))
        sc, body = _ec2("POST", "/events", ta, {
            "title": "E2E Test Event", "kind": "meetup", "date": fut,
            "format": "in_person", "description": "e2e", "status": "published", "is_public": True,
        })
        eid = (json.loads(body).get("id") if sc < 300 else None)
        check("event.create", sc in (200, 201) and eid, f"{sc} {body}")
        sc, body = _ec2("GET", f"/events/{eid}", ta)
        check("event.fetch_back", sc == 200 and eid and eid in body, f"{sc}")

        # ---- follow + watchlist ----
        sc, body = _ec2("POST", "/events/categories/pokemon/follow", ta, {})
        check("follow.category", sc == 200, f"{sc} {body}")
        sc, body = _ec2("POST", "/watchlist/mine", ta,
                        {"name": "E2E watch", "category": "pokemon", "currency": "EUR", "priority": "medium"})
        wid = (json.loads(body).get("id") if sc < 300 else None)
        check("watchlist.add", sc in (200, 201) and wid, f"{sc} {body}")
        if wid:
            sc, _ = _ec2("DELETE", f"/watchlist/mine/{wid}", ta)
            check("watchlist.remove", sc in (200, 204), f"{sc}")
    finally:
        _admin_delete(a)
        _admin_delete(b)

    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{'' if ok else '  -> ' + detail}")
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
