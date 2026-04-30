"""End-to-end verify Sets / Series / Master-set completion.

The `sets` table is currently empty (no ingestion worker), so a smoke
test of the read endpoints alone proves nothing about the write path
math. This verifier seeds a synthetic set with 3 items, exercises every
user action, asserts the contract, then cleans up. All against live EC2
+ Supabase.

Steps:
  1. seed: insert sets + 3 set_items rows
  2. listSets()                  → set appears
  3. listSets(category_id=lego)  → filter works
  4. getSetDetail(setId)          → 3 items, ordered by position
  5. updateSetProgress add [a,b]  → owned=2 pct=66.67
  6. updateSetProgress add [c]    → owned=3 pct=100.00 (tests dedup)
  7. updateSetProgress remove [b] → owned=2 pct=66.67
  8. getSetProgress(setId)        → reads back the 2 owned ids
  9. getMySetProgress()           → master-set view includes our set
 10. getAutoSetProgress           → smoke (returns empty if no items.attrs)
 11. cleanup: drop progress, set_items, set
"""
import os, json, urllib.request, urllib.error, time, jwt, asyncio, asyncpg, uuid

CI_TEST = "20503ad2-c62d-4700-810b-36da247bbf28"
CATEGORY = "lego"

secret = os.environ["SUPABASE_JWT_SECRET"]
issuer = os.environ.get("SUPABASE_JWT_ISSUER", "")

def mint(sub: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": sub, "aud": "authenticated", "role": "authenticated",
                       "iat": now, "exp": now + 3600, "iss": issuer},
                      secret, algorithm="HS256")

CI_TOKEN = mint(CI_TEST)
EC2 = "http://localhost:8000"

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

PACE = 1.5
res = []
def mark(label, ok, detail=""):
    res.append((label, ok, detail))
    print(f"  {'✓' if ok else '✗'} {label:55s}  {str(detail)[:120]}", flush=True)


async def main():
    conn = await asyncpg.connect(os.environ["DB_DSN_DIRECT"])
    await conn.execute("SET statement_timeout = 0")
    print(f"CI={CI_TEST}", flush=True)
    print("Cooldown 30s…", flush=True); time.sleep(30)

    set_id = str(uuid.uuid4())
    item_a, item_b, item_c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

    # Step 1: seed
    await conn.execute(
        "INSERT INTO public.sets (id, category_id, name, total_items) VALUES ($1::uuid, $2, $3, $4)",
        set_id, CATEGORY, f"E2E Test Set {uuid.uuid4().hex[:8]}", 3,
    )
    for idx, iid in enumerate([item_a, item_b, item_c]):
        await conn.execute(
            "INSERT INTO public.set_items (id, set_id, name, position) VALUES ($1::uuid, $2::uuid, $3, $4)",
            iid, set_id, f"Item {chr(65+idx)}", idx,
        )
    mark("seed: 1 set + 3 set_items inserted", True, f"set={set_id}")

    # Step 2: listSets — find our set
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", "/sets")
    out = json.loads(body) if code == 200 else {}
    sets = out.get("sets", []) if isinstance(out, dict) else []
    found = any(s.get("id") == set_id for s in sets)
    mark("listSets() → our set appears",
         code == 200 and found,
         f"HTTP {code} n_sets={len(sets)} found={found}")

    # Step 3: listSets filtered by category
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", f"/sets?category_id={CATEGORY}")
    out = json.loads(body) if code == 200 else {}
    sets = out.get("sets", []) if isinstance(out, dict) else []
    found = any(s.get("id") == set_id for s in sets)
    mark(f"listSets(category_id={CATEGORY}) → filter works",
         code == 200 and found,
         f"HTTP {code} n_sets={len(sets)}")

    # Step 4: getSetDetail
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", f"/sets/{set_id}")
    out = json.loads(body) if code == 200 else {}
    items = out.get("items", []) if isinstance(out, dict) else []
    positions_ok = all(items[i].get("position") == i for i in range(min(3, len(items))))
    mark("getSetDetail → 3 items in order",
         code == 200 and len(items) == 3 and positions_ok,
         f"HTTP {code} n_items={len(items)} positions_ok={positions_ok}")

    # Step 5: PUT progress add [a,b]
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "PUT", f"/sets/{set_id}/progress",
                         {"item_ids": [item_a, item_b], "action": "add"})
    out = json.loads(body) if code == 200 else {}
    mark("updateSetProgress add [a,b] → owned=2 pct=66.67",
         code == 200 and out.get("owned_count") == 2 and abs(out.get("completion_pct", 0) - 66.67) < 0.5,
         f"HTTP {code} owned={out.get('owned_count')} pct={out.get('completion_pct')}")

    # Step 6: PUT progress add [c] (also re-add a to test dedup)
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "PUT", f"/sets/{set_id}/progress",
                         {"item_ids": [item_a, item_c], "action": "add"})
    out = json.loads(body) if code == 200 else {}
    mark("updateSetProgress add [a,c] dedup → owned=3 pct=100",
         code == 200 and out.get("owned_count") == 3 and abs(out.get("completion_pct", 0) - 100.0) < 0.5,
         f"HTTP {code} owned={out.get('owned_count')} pct={out.get('completion_pct')}")

    # Step 7: PUT progress remove [b]
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "PUT", f"/sets/{set_id}/progress",
                         {"item_ids": [item_b], "action": "remove"})
    out = json.loads(body) if code == 200 else {}
    mark("updateSetProgress remove [b] → owned=2 pct=66.67",
         code == 200 and out.get("owned_count") == 2 and abs(out.get("completion_pct", 0) - 66.67) < 0.5,
         f"HTTP {code} owned={out.get('owned_count')} pct={out.get('completion_pct')}")

    # Step 8: getSetProgress reads back state
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", f"/sets/{set_id}/progress")
    out = json.loads(body) if code == 200 else {}
    owned = out.get("owned_item_ids", [])
    has_ac = item_a in owned and item_c in owned
    db_row = await conn.fetchrow(
        "SELECT owned_count, completion_pct FROM user_set_progress "
        "WHERE user_id = $1::uuid AND set_id = $2::uuid",
        CI_TEST, set_id,
    )
    mark("getSetProgress → reads back 2 owned ids",
         code == 200 and len(owned) == 2 and has_ac and db_row and db_row["owned_count"] == 2,
         f"HTTP {code} owned_ids={len(owned)} db_owned={db_row['owned_count'] if db_row else None}")

    # Step 9: getMySetProgress (master-set)
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", "/sets/my-progress")
    out = json.loads(body) if code == 200 else {}
    progress_rows = out.get("progress", []) if isinstance(out, dict) else []
    found_mine = any(p.get("set_id") == set_id and p.get("owned_count") == 2 for p in progress_rows)
    mark("getMySetProgress → master-set includes ours",
         code == 200 and found_mine,
         f"HTTP {code} n_rows={len(progress_rows)} found={found_mine}")

    # Step 10: auto-progress (smoke — empty when items.attrs has no set_name)
    time.sleep(PACE)
    code, body = hit_ec2(CI_TOKEN, "GET", "/sets/auto-progress")
    mark("getAutoSetProgress → 200 (no schema crash)",
         code == 200,
         f"HTTP {code} body={body[:80]}")

    # Cleanup
    print("\n=== CLEANUP ===", flush=True)
    await conn.execute(
        "DELETE FROM user_set_progress WHERE user_id = $1::uuid AND set_id = $2::uuid",
        CI_TEST, set_id,
    )
    await conn.execute("DELETE FROM set_items WHERE set_id = $1::uuid", set_id)
    await conn.execute("DELETE FROM sets WHERE id = $1::uuid", set_id)
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
