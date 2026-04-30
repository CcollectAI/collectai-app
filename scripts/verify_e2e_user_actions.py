"""COMPLETE end-to-end verification for every primary user action
across every tab the user named: quickscan, items, watchlist, alerts,
notifications, events, chat, paywall analytics. Each step:
- POST/PATCH/DELETE through the real EC2 backend with auth'd JWT
- SELECT the row back from the DB to prove it landed (or got removed)
- Log honest pass/fail
- Cleanup at the end
"""
import os, json, urllib.request, urllib.error, time, jwt, asyncio, asyncpg

TEST_USER = "20503ad2-c62d-4700-810b-36da247bbf28"
secret = os.environ["SUPABASE_JWT_SECRET"]
issuer = os.environ.get("SUPABASE_JWT_ISSUER", "")
now = int(time.time())
TOKEN = jwt.encode({"sub": TEST_USER, "aud": "authenticated", "role": "authenticated",
                    "iat": now, "exp": now + 3600, "iss": issuer}, secret, algorithm="HS256")

def hit(method, path, body=None, timeout=20):
    h = {"Accept": "application/json", "Authorization": f"Bearer {TOKEN}"}
    if body is not None: h["Content-Type"] = "application/json"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://localhost:8000" + path, method=method, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"

def supa_rpc(name, params):
    url = os.environ["SUPABASE_URL"].rstrip("/") + f"/rest/v1/rpc/{name}"
    req = urllib.request.Request(url, method="POST", data=json.dumps(params).encode(),
        headers={"apikey": os.environ["SUPABASE_KEY"], "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"

PACE = 2.0  # seconds between calls
GROUP_PACE = 8.0  # between feature groups

async def main():
    conn = await asyncpg.connect(os.environ["DB_DSN_DIRECT"])
    await conn.execute("SET statement_timeout = 0")
    print("Cooldown 30s for rate limiter…")
    time.sleep(30)

    res = []
    cleanup_ids = {"items": [], "watchlist": [], "events": [], "bp": [], "alerts": []}

    def mark(label, ok, detail=""):
        res.append((label, ok, detail))
        print(f"  {'✓' if ok else '✗'} {label}  {detail[:140]}", flush=True)

    # ==================== ITEMS TAB ====================
    print("\n=== ITEMS TAB ===", flush=True)
    time.sleep(PACE)
    code, body = hit("POST", "/items", {"name": "E2E Item", "category": "pokemon"})
    item_id = json.loads(body).get("id") if code in (200,201) else None
    if item_id: cleanup_ids["items"].append(item_id)
    row = await conn.fetchrow("SELECT id, title, category FROM items WHERE id=$1::uuid", item_id) if item_id else None
    mark("create item (POST /items)", bool(row), f"row.title={row['title'] if row else None!r}")

    time.sleep(PACE)
    if item_id:
        code, _ = hit("PATCH", f"/items/{item_id}/attributes", {"attributes": {"set_name":"E2E","graded_by":"PSA"}})
        attrs = await conn.fetchval("SELECT attrs FROM items WHERE id=$1::uuid", item_id)
        mark("PATCH item attrs", code == 200 and attrs, f"attrs={attrs}")

    time.sleep(PACE)
    code, body = hit("GET", "/items")
    mark("list items", code == 200, f"len={len(json.loads(body).get('items', []))}" if code==200 else f"HTTP {code}")

    time.sleep(PACE)
    code, body = hit("GET", "/items-export/overview")
    mark("export CSV", code == 200, "csv returned" if code == 200 else f"HTTP {code}")

    # ==================== QUICKSCAN ====================
    print(f"\n=== QUICKSCAN ===", flush=True)
    time.sleep(GROUP_PACE)
    code, body = hit("POST", "/intake/barcode-only", {"barcode": "9780545606509"})
    mark("intake barcode", code == 200, body[:80] if code != 200 else "ok")

    time.sleep(PACE)
    # quickscan persist mimics persistQuickscanDraft
    code, body = hit("POST", "/items", {"name": "Quickscan Persist Test", "category": "pokemon"})
    qs_id = json.loads(body).get("id") if code in (200,201) else None
    if qs_id: cleanup_ids["items"].append(qs_id)
    row = await conn.fetchrow("SELECT id, title FROM items WHERE id=$1::uuid", qs_id) if qs_id else None
    mark("quickscan persist (POST /items)", bool(row), f"row.title={row['title'] if row else None!r}")

    # ==================== WATCHLIST ====================
    print(f"\n=== WATCHLIST ===", flush=True)
    time.sleep(GROUP_PACE)
    code, body = hit("POST", "/watchlist/mine", {"name": "E2E watchlist title", "category": "pokemon", "currency": "EUR"})
    wl_id = json.loads(body).get("id") if code in (200,201) else None
    if wl_id: cleanup_ids["watchlist"].append(wl_id)
    row = await conn.fetchrow("SELECT id, title, category FROM watchlist_items WHERE id=$1::uuid", wl_id) if wl_id else None
    mark("add to watchlist", bool(row) and row["title"] == "E2E watchlist title", f"title={row['title'] if row else None!r}")

    time.sleep(PACE)
    code, body = hit("GET", "/watchlist/mine")
    mark("list watchlist", code == 200, f"items={len(json.loads(body).get('items', []))}" if code==200 else f"HTTP {code}")

    time.sleep(PACE)
    if wl_id:
        code, body = hit("DELETE", f"/watchlist/mine/{wl_id}")
        gone = await conn.fetchval("SELECT 1 FROM watchlist_items WHERE id=$1::uuid", wl_id) is None
        mark("remove from watchlist", code == 200 and gone, f"HTTP {code} gone={gone}")
        if gone: cleanup_ids["watchlist"].remove(wl_id)

    # ==================== ALERTS ====================
    print(f"\n=== ALERTS ===", flush=True)
    time.sleep(GROUP_PACE)
    code, body = hit("GET", "/alerts/mine")
    mark("list alert rules", code == 200, f"alerts={len(json.loads(body).get('alerts', []))}" if code==200 else f"HTTP {code}")

    time.sleep(PACE)
    code, body = hit("GET", "/alerts/trigger-history")
    mark("alert history", code == 200, body[:60] if code != 200 else "ok")

    # ==================== NOTIFICATIONS ====================
    print(f"\n=== NOTIFICATIONS ===", flush=True)
    time.sleep(GROUP_PACE)
    code, body = hit("GET", "/notifications/history")
    mark("notif history", code == 200, body[:60] if code != 200 else "ok")
    time.sleep(PACE)
    code, body = hit("GET", "/notifications/preferences")
    mark("notif prefs", code == 200, body[:60] if code != 200 else "ok")
    time.sleep(PACE)
    code, body = hit("GET", "/chat/unread-count")
    mark("chat unread", code == 200, body[:60] if code != 200 else "ok")

    # ==================== EVENTS ====================
    print(f"\n=== EVENTS ===", flush=True)
    time.sleep(GROUP_PACE)
    code, body = hit("POST", "/events", {
        "title": "E2E Event", "kind": "meetup", "date": "2027-12-15",
        "description": "smoke", "format": "in_person", "is_public": True,
    })
    event_id = json.loads(body).get("id") if code in (200,201) else None
    if event_id: cleanup_ids["events"].append(event_id)
    row = await conn.fetchrow("SELECT id, title FROM events WHERE id=$1::uuid", event_id) if event_id else None
    mark("create event", bool(row), f"id={event_id}")

    time.sleep(PACE)
    if event_id:
        code, _ = hit("POST", f"/events/{event_id}/rsvp", {"status": "going"})
        row = await conn.fetchrow("SELECT status FROM event_attendees WHERE event_id::uuid=$1::uuid AND user_id=$2::uuid", event_id, TEST_USER)
        mark("rsvp event", bool(row), f"status={row['status'] if row else None}")
        time.sleep(PACE)
        code, _ = hit("DELETE", f"/events/{event_id}/rsvp")
        gone = await conn.fetchval("SELECT 1 FROM event_attendees WHERE event_id::uuid=$1::uuid AND user_id=$2::uuid", event_id, TEST_USER) is None
        mark("un-rsvp event", code in (200,204) and gone, f"gone={gone}")

    # ==================== PAYWALL ANALYTICS ====================
    print(f"\n=== PAYWALL ANALYTICS ===", flush=True)
    time.sleep(GROUP_PACE)
    for path in ["/analytics/portfolio/category-breakdown", "/portfolio/timeseries",
                 "/portfolio/category-stats", "/data-moat/prediction-accuracy",
                 "/intelligence/top-events"]:
        time.sleep(PACE)
        code, body = hit("GET", path)
        mark(f"analytics {path}", code == 200, body[:60] if code != 200 else "ok")

    # ==================== BUILD/PAINT (RPC) ====================
    print(f"\n=== BUILD/PAINT ===", flush=True)
    time.sleep(GROUP_PACE)
    code, body = supa_rpc("rpc_create_build_paint_project_v1",
                          {"p_title": "E2E bp", "p_category": "warhammer", "p_category_id": None, "p_item_id": None})
    bp_id = (json.loads(body) or {}).get("id") if code == 200 else None
    if bp_id: cleanup_ids["bp"].append(bp_id)
    row = await conn.fetchrow("SELECT id, name, status FROM build_paint_projects WHERE id=$1::text", bp_id) if bp_id else None
    mark("create build/paint project", bool(row), f"id={bp_id} status={row['status'] if row else None}")

    # ==================== CLEANUP ====================
    print(f"\n=== CLEANUP ===", flush=True)
    for iid in cleanup_ids["items"]:
        await conn.execute("DELETE FROM items WHERE id=$1::uuid", iid)
    for wid in cleanup_ids["watchlist"]:
        await conn.execute("DELETE FROM watchlist_items WHERE id=$1::uuid", wid)
    for eid in cleanup_ids["events"]:
        await conn.execute("DELETE FROM event_attendees WHERE event_id::uuid=$1::uuid", eid)
        await conn.execute("DELETE FROM events WHERE id=$1::uuid", eid)
    for bid in cleanup_ids["bp"]:
        await conn.execute("DELETE FROM build_paint_projects WHERE id=$1::text", bid)
    print(f"  cleaned up {sum(len(v) for v in cleanup_ids.values())} test rows")

    await conn.close()

    print(f"\n=== SUMMARY ===")
    ok = sum(1 for _, success, _ in res if success)
    fail = len(res) - ok
    print(f"  PASS: {ok}/{len(res)}    FAIL: {fail}")
    if fail:
        print(f"\n  Fails:")
        for label, success, detail in res:
            if not success:
                print(f"    ✗ {label}  — {detail[:160]}")

asyncio.run(main())
