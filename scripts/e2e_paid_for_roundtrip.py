"""E2E round-trip for items.purchase_* columns (the "paid for" surface).

Verifies the full FE↔DB contract that the items screen depends on:

  1. Write side — INSERT a test item with purchase_price_eur,
     purchase_currency, purchased_at, purchase_notes (mirrors the columns
     written by app/add-manual.tsx).
  2. Read side — fetch via the PostgREST projection that the FE uses
     verbatim (src/data/providers/itemsProvider.ts:ITEMS_SELECT). This is
     the projection that returned [] for months because of column drift —
     this test pins the contract so the next drift fails loudly.
  3. Assert every paid_for field round-trips intact.
  4. DELETE the test row.

Run on EC2 (or any host with DB_DSN + SUPABASE_URL + SUPABASE_KEY set):

    python3 scripts/e2e_paid_for_roundtrip.py

Exit 0 on full pass, 1 on any mismatch. Prints a per-field PASS/FAIL line.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import asyncpg
import urllib.error
import urllib.request
import json as _json


# Same projection string used by the FE (mirror of
# src/data/providers/itemsProvider.ts ITEMS_SELECT). When that constant
# changes, this string must change too — that's the point.
FE_ITEMS_SELECT = (
    "id,title,category,updated_at,attrs,collection_name,image_url,"
    "purchase_price_eur,purchase_currency,purchased_at,purchase_notes,"
    "quick_predictions(q50_eur,confidence,created_at)"
)


def _need_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"FAIL  missing env var: {name}", file=sys.stderr)
        sys.exit(2)
    return val


def _postgrest_get(supabase_url: str, anon_key: str, jwt: str | None, item_id: str) -> dict:
    """Fetch a single item via the same PostgREST projection the FE uses."""
    url = f"{supabase_url.rstrip('/')}/rest/v1/items?id=eq.{item_id}&select={FE_ITEMS_SELECT}"
    headers = {
        "apikey": anon_key,
        # Use the user's JWT when available so RLS sees the row owner.
        # Without it, PostgREST returns [] under default RLS — that would
        # be a false negative for this test, so fail loud.
        "Authorization": f"Bearer {jwt or anon_key}",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"PostgREST {e.code}: {body}") from None
    rows = _json.loads(body)
    if not rows:
        raise RuntimeError(f"PostgREST returned [] for id={item_id} (RLS hiding row?)")
    return rows[0]


async def main() -> int:
    db_dsn = _need_env("DB_DSN_DIRECT") if os.environ.get("DB_DSN_DIRECT") else _need_env("DB_DSN")
    supabase_url = _need_env("SUPABASE_URL")
    # Prefer service-role key for this test — bypasses RLS, mirrors the
    # "row exists" question rather than the "user can see it" question.
    # The FE's ITEMS_SELECT projection works the same regardless.
    anon_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY") or _need_env("SUPABASE_ANON_KEY")
    jwt = os.environ.get("TEST_USER_JWT")  # optional

    # Pick a test user_id — prefer an explicit env var, fall back to a
    # well-known seeded user so we don't have to mint one. The user_id
    # only has to satisfy the FK on items.user_id; RLS is bypassed via
    # the service-role key when available.
    test_user_id = os.environ.get("TEST_USER_ID")
    item_id = str(uuid.uuid4())
    # items.purchased_at is `timestamp with time zone`, not `date`. Confirmed
    # 2026-05-01 via information_schema.columns. Send a tz-aware UTC datetime
    # so the round-trip doesn't shift by the server's local TZ offset.
    purchased_at = datetime(2024, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
    inserted = {
        "id": item_id,
        "user_id": None,  # filled below if test_user_id available
        "title": f"E2E paid-for round-trip {int(time.time())}",
        "category": "pokemon",
        "purchase_price_eur": 250.0,
        "purchase_currency": "EUR",
        "purchased_at": purchased_at,
        "purchase_notes": "Local card shop",
    }

    conn = await asyncpg.connect(db_dsn)
    cleanup_id: str | None = None
    failures: list[str] = []
    try:
        # If no test_user_id provided, pick an existing user_id from the DB
        # so the FK / NOT NULL constraint is satisfied. Read-only — we never
        # mint or modify auth users from this test.
        if not test_user_id:
            row = await conn.fetchrow(
                "SELECT id FROM auth.users ORDER BY created_at LIMIT 1"
            )
            if not row:
                print("FAIL  no auth.users in DB; set TEST_USER_ID to override", file=sys.stderr)
                return 2
            test_user_id = str(row["id"])
        inserted["user_id"] = test_user_id

        # ----- WRITE SIDE -----
        await conn.execute(
            """
            INSERT INTO public.items
                (id, user_id, title, category,
                 purchase_price_eur, purchase_currency,
                 purchased_at, purchase_notes,
                 source, created_at, updated_at)
            VALUES ($1, $2::uuid, $3, $4,
                    $5, $6,
                    $7, $8,
                    'manual', now(), now())
            """,
            inserted["id"],
            inserted["user_id"],
            inserted["title"],
            inserted["category"],
            inserted["purchase_price_eur"],
            inserted["purchase_currency"],
            inserted["purchased_at"],
            inserted["purchase_notes"],
        )
        cleanup_id = inserted["id"]
        print(f"PASS  insert  items.id={item_id}")

        # ----- READ SIDE (PostgREST, same projection as the FE) -----
        try:
            row = _postgrest_get(supabase_url, anon_key, jwt, item_id)
        except Exception as e:
            print(f"FAIL  postgrest read: {e}")
            return 1
        print(f"PASS  postgrest projection returned a row")

        # ----- FIELD-LEVEL ASSERTIONS -----
        def check(field: str, want: object, got: object) -> None:
            if str(got) == str(want):
                print(f"PASS  {field}: {got!r}")
            else:
                failures.append(f"{field}: want {want!r}, got {got!r}")
                print(f"FAIL  {field}: want {want!r}, got {got!r}")

        check("id", inserted["id"], row.get("id"))
        check("title", inserted["title"], row.get("title"))
        check("category", inserted["category"], row.get("category"))
        check("purchase_price_eur", inserted["purchase_price_eur"], row.get("purchase_price_eur"))
        check("purchase_currency", inserted["purchase_currency"], row.get("purchase_currency"))
        # PostgREST serializes timestamptz as ISO 8601 with offset (e.g.
        # 2024-12-15T12:00:00+00:00). Compare against the same format we
        # sent — tz-aware UTC datetime → isoformat() with explicit offset.
        check("purchased_at", inserted["purchased_at"].isoformat(), row.get("purchased_at"))
        check("purchase_notes", inserted["purchase_notes"], row.get("purchase_notes"))

        # Optional: confirm the projection list itself didn't drop columns
        # by silently returning a subset. Fail if any of the paid-for keys
        # are missing entirely from the response.
        for key in ("purchase_price_eur", "purchase_currency", "purchased_at", "purchase_notes"):
            if key not in row:
                failures.append(f"projection missing key: {key}")
                print(f"FAIL  projection missing key: {key}")
            else:
                print(f"PASS  projection includes {key}")

    finally:
        if cleanup_id:
            await conn.execute(
                "DELETE FROM public.items WHERE id = $1::uuid",
                cleanup_id,
            )
            print(f"PASS  cleanup  deleted items.id={cleanup_id}")
        await conn.close()

    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nALL PASS — paid-for round-trip green")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
