"""End-to-end verify the Categories tab.

Covers every primary user action that touches category-shaped data:
  1. listCategorySummaries        — supabase.from('v_category_summaries_v1')
  2. listCategoryMissing          — supabase.from('v_category_missing_items_v1')
  3. browseCatalogItems           — GET /catalog/{cat}/items (EC2)
  4. followCategory               — POST /events/categories/{cat}/follow (EC2)
  5. listFollowedCategories       — GET /events/categories/followed (EC2)
  6. isFollowingCategory          — GET /events/categories/{cat}/following (EC2)
  7. unfollowCategory             — DELETE /events/categories/{cat}/follow (EC2)
  8. submitCatalogSuggestion      — POST /catalog/suggest (EC2)
  9. listMySuggestions            — GET /catalog/suggestions/mine (EC2)
 10. markCategoryItemOwned        — supabase.rpc('rpc_mark_category_item_owned_v1')
 11. getCategoryStore items query — supabase.from('items').select('images') sanity

Each step: real auth, real call, real DB readback. No mocks.
"""
import os, json, urllib.request, urllib.error, time, jwt, asyncio, asyncpg, uuid

CI_TEST = "20503ad2-c62d-4700-810b-36da247bbf28"
CATEGORY = "lego"  # has 3.4k items in category_items
SAMPLE_CATEGORY_ITEM = "31a209ec-6299-465c-a7f6-6996e7eb3bc6"  # lego sample row

secret = os.environ["SUPABASE_JWT_SECRET"]
issuer = os.environ.get("SUPABASE_JWT_ISSUER", "")

def mint(sub: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "aud": "authenticated", "role": "authenticated",
                       "iat": now, "exp": now + 3600, "iss": issuer},
                      secret, algorithm="HS256")

CI_TOKEN = mint(CI_TEST)
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
    print(f"  {'✓' if ok else '✗'} {label:55s}  {str(detail)[:120]}", flush=True)


async def main():
    conn = await asyncpg.connect(os.environ["DB_DSN_DIRECT"])
    await conn.execute("SET statement_timeout = 0")
    print(f"CI={CI_TEST}  CATEGORY={CATEGORY}", flush=True)
    print("Cooldown 30s…", flush=True); time.sleep(30)

    # Step 1: listCategorySummaries — Supabase view
    time.sleep(PACE)
    code, data = supa_select(CI_TOKEN, "v_category_summaries_v1",
                             "select=id,name,completion_pct,owned_count,missing_count,total_count&limit=5")
    rows = data if isinstance(data, list) else []
    mark("listCategorySummaries (v_category_summaries_v1)",
         code == 200 and isinstance(rows, list),
         f"HTTP {code} n_rows={len(rows)}")

    # Step 2: listCategoryMissing — Supabase view
    time.sleep(PACE)
    code, data = supa_select(CI_TOKEN, "v_category_missing_items_v1",
                             f"select=id,category_id,title,brand,notes&category_id=eq.{CATEGORY}&limit=5")
    rows = data if isinstance(data, list) else []
    mark("listCategoryMissing (v_category_missing_items_v1)",
         code == 200 and isinstance(rows, list),
         f"HTTP {code} n_rows={len(rows)}")

    # Step 3: browseCatalogItems via EC2
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", f"/catalog/{CATEGORY}/items?limit=3")
    out = json.loads(body) if code == 200 else {}
    items = out.get("items", []) if isinstance(out, dict) else []
    mark("browseCatalogItems GET /catalog/{cat}/items",
         code == 200 and isinstance(items, list) and len(items) >= 1,
         f"HTTP {code} n_items={len(items)} total={out.get('total') if isinstance(out, dict) else None}")

    # Step 4: followCategory via EC2
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "POST", f"/events/categories/{CATEGORY}/follow", {})
    row = await conn.fetchrow(
        "SELECT user_id, category_id FROM user_category_follows WHERE user_id = $1::uuid AND category_id = $2",
        CI_TEST, CATEGORY,
    )
    mark("followCategory → user_category_follows row",
         code == 200 and bool(row),
         f"HTTP {code} row={dict(row) if row else None}")

    # Step 5: listFollowedCategories via EC2 — VERIFY FE/BE SHAPE MISMATCH
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", "/events/categories/followed")
    out = json.loads(body) if code == 200 else {}
    cats = out.get("categories", []) if isinstance(out, dict) else []
    # Server returns string[] (e.g., ["lego"]); FE provider treats it as
    # {category_id: string}[] then maps r.category_id → undefined. Capture
    # the actual server shape so we can prove or refute the mismatch.
    is_string_array = bool(cats) and isinstance(cats[0], str)
    is_obj_array = bool(cats) and isinstance(cats[0], dict) and "category_id" in cats[0]
    mark("listFollowedCategories GET /events/categories/followed",
         code == 200 and CATEGORY in (cats if is_string_array else [c.get("category_id") for c in cats] if is_obj_array else []),
         f"HTTP {code} shape={'string[]' if is_string_array else 'obj[]' if is_obj_array else 'unknown'} cats={cats}")

    # Step 6: isFollowingCategory via EC2
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", f"/events/categories/{CATEGORY}/following")
    out = json.loads(body) if code == 200 else {}
    mark("isFollowingCategory → following=true",
         code == 200 and out.get("following") is True,
         f"HTTP {code} body={body[:80]}")

    # Step 7: unfollowCategory via EC2
    time.sleep(PACE)
    code, _ = hit_ec2(CI_TOKEN, "DELETE", f"/events/categories/{CATEGORY}/follow")
    row = await conn.fetchrow(
        "SELECT user_id FROM user_category_follows WHERE user_id = $1::uuid AND category_id = $2",
        CI_TEST, CATEGORY,
    )
    mark("unfollowCategory → row gone",
         code == 200 and row is None,
         f"HTTP {code} row={row}")

    # Step 8: submitCatalogSuggestion via EC2
    time.sleep(PACE)
    nonce = uuid.uuid4().hex[:8]
    payload = {
        "source": "manual",
        "input_data": {"nonce": nonce},
        "suggested_name": f"E2E Test Suggestion {nonce}",
        "suggested_category": CATEGORY,
    }
    code, body = hit_ec2(CI_TOKEN, "POST", "/catalog/suggest", payload)
    out = json.loads(body) if code in (200, 201) else {}
    suggestion_id = out.get("id") if isinstance(out, dict) else None
    db_row = await conn.fetchrow(
        "SELECT id, status, suggested_name FROM catalog_suggestions WHERE id = $1::uuid",
        suggestion_id,
    ) if suggestion_id else None
    mark("submitCatalogSuggestion → catalog_suggestions row",
         code in (200, 201) and bool(db_row) and db_row["suggested_name"] == payload["suggested_name"],
         f"HTTP {code} id={suggestion_id} status={db_row['status'] if db_row else None}")

    # Step 9: listMySuggestions via EC2
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", "/catalog/suggestions/mine")
    out = json.loads(body) if code == 200 else {}
    sug_list = out.get("suggestions", out.get("items", [])) if isinstance(out, dict) else []
    found_mine = any(s.get("id") == suggestion_id for s in sug_list) if suggestion_id else False
    mark("listMySuggestions GET /catalog/suggestions/mine",
         code == 200 and found_mine,
         f"HTTP {code} n={len(sug_list)} found_mine={found_mine}")

    # Step 10: markCategoryItemOwned via Supabase RPC
    time.sleep(PACE)
    code, body = supa_rpc(CI_TOKEN, "rpc_mark_category_item_owned_v1", {
        "p_category_item_id": SAMPLE_CATEGORY_ITEM,
        "p_quantity": 1,
        "p_notes": f"e2e {nonce}",
    })
    db_row = await conn.fetchrow(
        "SELECT id, quantity, notes FROM user_category_ownership "
        "WHERE user_id = $1::uuid AND category_item_id = $2::uuid",
        CI_TEST, SAMPLE_CATEGORY_ITEM,
    )
    mark("markCategoryItemOwned → user_category_ownership row",
         code in (200, 204) and bool(db_row) and db_row["quantity"] >= 1,
         f"HTTP {code} row={dict(db_row) if db_row else None}")

    # Step 11: getCategoryStore items query, FE-shape after the column-drift
    # fix (image_url not images, name as primary). Earlier version hit a 400
    # on `images` and silently returned [] for every category store open.
    time.sleep(PACE)
    code, data = supa_select(
        CI_TOKEN, "items",
        f"select=id,name,title,category,updated_at,image_url&category=eq.{CATEGORY}&limit=1",
    )
    fe_query_works = code == 200 and isinstance(data, list)
    mark("getCategoryStore items SELECT (FE-shape after fix)",
         fe_query_works,
         f"HTTP {code} n={len(data) if isinstance(data, list) else None}")

    # Cleanup
    print("\n=== CLEANUP ===", flush=True)
    if suggestion_id:
        await conn.execute("DELETE FROM catalog_suggestions WHERE id = $1::uuid", suggestion_id)
    await conn.execute(
        "DELETE FROM user_category_ownership WHERE user_id = $1::uuid AND category_item_id = $2::uuid",
        CI_TEST, SAMPLE_CATEGORY_ITEM,
    )
    print("  cleaned up")
    await conn.close()

    ok = sum(1 for _, success, _ in res if success)
    print(f"\n=== SUMMARY ===")
    print(f"  PASS: {ok}/{len(res)}    FAIL: {len(res) - ok}")
    if ok != len(res):
        print(f"\n  FAILS:")
        for label, success, detail in res:
            if not success:
                print(f"    ✗ {label}  — {str(detail)[:200]}")

asyncio.run(main())
