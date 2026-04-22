"""E2E test the 4 Pro features against the live bake API.

For each endpoint:
  1. Pick a real item_ref from category_items
  2. Call the endpoint as a service-role user
  3. Report status code + payload shape + whether data is real

Covered:
  - GET  /predict/trend/{item_ref}?days=90   → PriceTrendChart
  - GET  /dossier/{item_ref}                 → Valuation Report
  - GET  /provenance/items/{item_ref}        → Item History
  - POST /marketplace/search                 → Market Prices (query-based)
"""

import asyncio, asyncpg, os, httpx, json


BASE = "http://localhost:8000"


async def get_token(email: str, password: str) -> str:
    """Log in as the test user and return a Supabase JWT."""
    url = f"{os.environ['SUPABASE_URL']}/auth/v1/token?grant_type=password"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            url,
            json={"email": email, "password": password},
            headers={"apikey": os.environ["SUPABASE_ANON_KEY"]},
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def main():
    # pick a real item_ref we know has data
    conn = await asyncpg.connect(os.environ["DB_DSN"], timeout=30)
    row = await conn.fetchrow(
        "SELECT item_ref FROM public.price_predictions "
        "WHERE category='mtg' AND q50 IS NOT NULL "
        "ORDER BY generated_at DESC LIMIT 1"
    )
    item_ref = row["item_ref"] if row else None
    print(f"item_ref for test: {item_ref!r}")
    if not item_ref:
        print("no test item — skipping")
        return
    await conn.close()

    tok = await get_token(os.environ["TEST_EMAIL"], os.environ["TEST_PASSWORD"])
    headers = {"Authorization": f"Bearer {tok}"}

    async with httpx.AsyncClient(base_url=BASE, timeout=30, headers=headers) as c:
        # 1. Price Trend
        r = await c.get(f"/predict/trend/{item_ref}", params={"days": 90})
        print(f"\n[1] Price Trend: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"   data_points: {len(d.get('data_points', []))}")
            print(f"   direction:   {d.get('direction')}")
            print(f"   pct_change:  {d.get('pct_change')}")
            print(f"   current_q50: {d.get('current_q50')}")
        else:
            print(f"   body: {r.text[:200]}")

        # 2. Dossier (Valuation Report)
        r = await c.get(f"/dossier/{item_ref}")
        print(f"\n[2] Valuation Report (Dossier): {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"   keys: {list(d.keys())[:8]}")
        else:
            print(f"   body: {r.text[:200]}")

        # 3. Provenance (Item History)
        r = await c.get(f"/provenance/items/{item_ref}")
        print(f"\n[3] Item History (Provenance): {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            events = d.get("events") or d.get("items") or []
            print(f"   events: {len(events) if isinstance(events, list) else '<non-list>'}")
            print(f"   keys: {list(d.keys())[:8]}")
        else:
            print(f"   body: {r.text[:200]}")

        # 4. Marketplace Search
        r = await c.post("/marketplace/search", json={"query": "Black Lotus"})
        print(f"\n[4] Marketplace Search: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            hits = d.get("hits") or d.get("results") or []
            print(f"   hits: {len(hits) if isinstance(hits, list) else '<non-list>'}")
            print(f"   keys: {list(d.keys())[:6]}")
        else:
            print(f"   body: {r.text[:200]}")


asyncio.run(main())
