import os, math, asyncio, asyncpg, ssl

SUPABASE_HOST = os.getenv("SUPABASE_HOST")
SUPABASE_DB   = os.getenv("SUPABASE_DB")
SUPABASE_USER = os.getenv("SUPABASE_USER")
SUPABASE_PASS = os.getenv("SUPABASE_PASS")
SUPABASE_PORT = int(os.getenv("SUPABASE_PORT","5432"))
USE_MV = os.getenv("Q50_USE_CLAMP_MV","1") == "1"
READ_VIEW = "public.price_samples_clamped_mv_v1" if USE_MV else "public.price_samples_clamped_v1"

async def _connect():
    return await asyncpg.connect(
        user=SUPABASE_USER, password=SUPABASE_PASS, database=SUPABASE_DB,
        host=SUPABASE_HOST, port=SUPABASE_PORT, ssl=ssl.create_default_context()
    )

def weighted_median(pairs):
    if not pairs: return None
    pairs = sorted(pairs, key=lambda x: x[0])
    total = sum(w for _,w in pairs)
    if total <= 0: return None
    acc = 0.0; half = total/2.0
    for p,w in pairs:
        acc += w
        if acc >= half: return p
    return pairs[-1][0]

async def fetch_samples(conn, category):
    rows = await conn.fetch(f"""
      select price::numeric as price, coalesce(effective_weight,1.0) as w
      from {READ_VIEW}
      where category = $1 and price is not null and (is_iqr_outlier is false or is_iqr_outlier is null)
      order by ts desc
      limit 5000
    """, category)
    return [(float(r["price"]), float(r["w"])) for r in rows]

async def write_prediction(conn, category, q50_value):
    await conn.execute("""
      insert into public.price_predictions (ts, category, head, q50)
      values (now(), $1, 'v0.3-iqr-weighted', $2)
      on conflict (ts, category, head) do update set q50 = excluded.q50
    """, category, q50_value)

async def categories(conn):
    rows = await conn.fetch(f"select distinct category from {READ_VIEW} where price is not null limit 2000;")
    return [r["category"] for r in rows if r["category"]]

async def main():
    conn = await _connect()
    try:
        updated = 0
        for c in await categories(conn):
            samples = await fetch_samples(conn, c)
            if not samples: continue
            q50 = weighted_median(samples)
            if q50 is None: continue
            await write_prediction(conn, c, q50)
            updated += 1
        print(f"[v0.3] updated categories: {updated}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
