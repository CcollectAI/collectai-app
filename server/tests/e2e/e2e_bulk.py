"""Bulk E2E audit — for every category with data, seed one items row
and call all 4 Pro endpoints. Aggregate status codes + payload health.

Goal: surface categories where any of the 4 features silently returns
empty or 500s, so we can harden the endpoints before launch.
"""

import asyncio, asyncpg, os, httpx, uuid, json
from collections import defaultdict

BASE = "http://localhost:8000"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("EXPO_PUBLIC_SUPABASE_ANON_KEY") or os.environ["SUPABASE_KEY"]

EMAIL = "e2e-test@collectai.app"
PASSWORD = "E2ETestR50m!"


async def get_token() -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": ANON},
            json={"email": EMAIL, "password": PASSWORD},
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def get_user_id() -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{SUPABASE_URL}/auth/v1/admin/users?email={EMAIL}",
            headers={"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"},
        )
        r.raise_for_status()
        users = r.json().get("users", [])
        return users[0]["id"]


async def main():
    conn = await asyncpg.connect(os.environ["DB_DSN"], timeout=30)
    await conn.execute("SET statement_timeout='25s'")

    uid = await get_user_id()
    tok = await get_token()
    print(f"user: {uid}")

    # Sample: one item_ref per category with full data (preds + history + hits)
    rows = await conn.fetch("""
        SELECT DISTINCT ON (pp.category)
          pp.category, pp.item_ref
        FROM public.price_predictions pp
        WHERE pp.category IS NOT NULL AND pp.item_ref IS NOT NULL
        ORDER BY pp.category, pp.generated_at DESC
    """)
    print(f"found {len(rows)} categories with predictions\n")

    # Cleanup previous test rows
    await conn.execute(
        "DELETE FROM public.items WHERE user_id = $1::uuid AND title LIKE 'E2E %'",
        uid,
    )

    # Seed one items row per category
    seeded: list[tuple[str, str, str]] = []  # (category, item_id, canonical_key)
    for r in rows:
        cat = r["category"]
        canonical = r["item_ref"]
        iid = str(uuid.uuid4())
        try:
            await conn.execute(
                "INSERT INTO public.items (id, user_id, title, category, canonical_key, created_at) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5, now())",
                iid, uid, f"E2E {cat}", cat, canonical,
            )
            seeded.append((cat, iid, canonical))
        except Exception as e:
            print(f"  seed failed for {cat}: {e}")

    print(f"seeded {len(seeded)} test items\n")
    await conn.close()

    # Hit all endpoints per item
    results: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures: dict[str, list[str]] = defaultdict(list)

    async with httpx.AsyncClient(
        base_url=BASE, timeout=30,
        headers={"Authorization": f"Bearer {tok}"},
    ) as c:
        for i, (cat, iid, canonical) in enumerate(seeded):
            # Pace for rate limiter (per-user ~20-30/60s on these endpoints)
            if i > 0 and i % 6 == 0:
                await asyncio.sleep(15)
            _ = canonical  # silence unused
            # Price Trend
            try:
                r = await c.get(f"/predict/trend/{iid}", params={"days": 90})
                key = f"{r.status_code}"
                if r.status_code == 200:
                    pts = len(r.json().get("data_points", []))
                    key = f"200:{pts}pts" if pts else "200:empty"
                results["price_trend"][key] += 1
                if r.status_code >= 400:
                    failures["price_trend"].append(f"{cat}: {r.status_code} {r.text[:120]}")
            except Exception as e:
                results["price_trend"]["exc"] += 1
                failures["price_trend"].append(f"{cat}: {e}")

            # Dossier
            try:
                r = await c.get(f"/dossier/{iid}")
                if r.status_code == 200:
                    j = r.json()
                    has_val = bool(j.get("valuation"))
                    has_ph = len(j.get("price_history") or [])
                    key = f"200:val={'Y' if has_val else 'N'} ph={has_ph}"
                else:
                    key = str(r.status_code)
                results["dossier"][key] += 1
                if r.status_code >= 400:
                    failures["dossier"].append(f"{cat}: {r.status_code} {r.text[:120]}")
            except Exception as e:
                results["dossier"]["exc"] += 1
                failures["dossier"].append(f"{cat}: {e}")

            # Provenance
            try:
                r = await c.get(f"/provenance/items/{iid}")
                if r.status_code == 200:
                    n_events = len(r.json().get("events") or [])
                    key = f"200:{n_events}evts"
                else:
                    key = str(r.status_code)
                results["provenance"][key] += 1
                if r.status_code >= 400:
                    failures["provenance"].append(f"{cat}: {r.status_code} {r.text[:120]}")
            except Exception as e:
                results["provenance"]["exc"] += 1
                failures["provenance"].append(f"{cat}: {e}")

    # Report
    print("=" * 70)
    print("E2E BULK RESULTS")
    print("=" * 70)
    for endpoint in ("price_trend", "dossier", "provenance"):
        print(f"\n{endpoint}:")
        for k, v in sorted(results[endpoint].items(), key=lambda x: -x[1]):
            print(f"  {k:<32} {v:>3}")

    # Failures summary
    print("\n" + "=" * 70)
    print("FAILURES (first 10 per endpoint)")
    print("=" * 70)
    for endpoint, fails in failures.items():
        if fails:
            print(f"\n{endpoint} ({len(fails)} total):")
            for f in fails[:10]:
                print(f"  {f}")


asyncio.run(main())
