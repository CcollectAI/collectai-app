#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[apply_v0_3] failed at line $LINENO (exit=$?)"' ERR

echo "[apply_v0_3] cwd=$(pwd)"

# 0) Ensure tree
mkdir -p db/migrations db/cron db/backtests heads ops/exporter

# 1) v0.3 migration (weights + views + MV)
cat > db/migrations/2025-10-17-v0.3.sql <<'SQL'
-- v0.3 additive migration: source weights + IQR/weighted views + MV

create table if not exists public.source_weights (
  source text primary key,
  base_weight numeric not null default 1.0,
  decay_half_life_days int
);

insert into public.source_weights (source, base_weight, decay_half_life_days) values
  ('ebay',      1.00, 30),
  ('tcgplayer', 1.15, 21),
  ('whatnot',   0.90, 14),
  ('mercari',   0.85, 21)
on conflict (source) do update
  set base_weight = excluded.base_weight,
      decay_half_life_days = excluded.decay_half_life_days;

create or replace view public.price_samples_enriched_v1 as
select
  mh.category,
  mh.price::numeric as price,
  mh.currency,
  mh.ts,
  mh.source,
  coalesce(mh.volume, 1) as volume,
  mh.title,
  mh.condition,
  sw.base_weight,
  sw.decay_half_life_days,
  case
    when sw.decay_half_life_days is null then 1.0
    else power(0.5, greatest(0, extract(epoch from (now() - mh.ts))/86400.0) / sw.decay_half_life_days)
  end as time_decay,
  ln(least(1000, greatest(1, coalesce(mh.volume,1))) + 1) as volume_lift
from public.market_hits mh
left join public.source_weights sw on sw.source = mh.source;

create or replace view public.price_samples_weighted_v1 as
select
  *,
  coalesce(base_weight,1.0)*coalesce(time_decay,1.0)*coalesce(volume_lift,1.0) as effective_weight
from public.price_samples_enriched_v1;

create or replace view public.price_samples_clamped_v1 as
with q as (
  select category,
         percentile_cont(0.25) within group (order by price) as q1,
         percentile_cont(0.75) within group (order by price) as q3
  from public.price_samples_weighted_v1
  group by category
)
select
  w.*,
  q.q1, q.q3,
  (q.q3 - q.q1) as iqr,
  case when w.price < q.q1 - 1.5*(q.q3 - q.q1)
        or w.price > q.q3 + 1.5*(q.q3 - q.q1)
       then true else false end as is_iqr_outlier
from public.price_samples_weighted_v1 w
join q on q.category = w.category;

create materialized view if not exists public.price_samples_clamped_mv_v1 as
select * from public.price_samples_clamped_v1
where price is not null;

create index if not exists idx_psc_mv_v1_cat_ts on public.price_samples_clamped_mv_v1 (category, ts desc);

grant select on public.source_weights to anon, authenticated, service_role;
grant select on public.price_samples_enriched_v1 to anon, authenticated, service_role;
grant select on public.price_samples_weighted_v1 to anon, authenticated, service_role;
grant select on public.price_samples_clamped_v1 to anon, authenticated, service_role;
grant select on public.price_samples_clamped_mv_v1 to anon, authenticated, service_role;
SQL

# 2) v0.3 q50 head (IQR + weighted median)
cat > heads/q50_head.py <<'PY'
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
PY

# 3) cron helper (refresh MV)
cat > db/cron/refresh_v0_3.sql <<'SQL'
refresh materialized view concurrently public.price_samples_clamped_mv_v1;
SQL

# 4) dormant item-level backtest (gated on item_ref)
cat > db/backtests/item_backtest.sql <<'SQL'
do $$
begin
  if exists (
    select 1 from information_schema.columns
     where table_schema='public' and table_name='market_hits' and column_name='item_ref'
  ) then
    create or replace view public.item_backtest_v1 as
    with items as (
      select item_ref, category, price::numeric as price, ts
      from public.market_hits where item_ref is not null
    ),
    preds as (
      select item_ref, q50, ts from public.price_predictions_item
    )
    select i.category, i.item_ref,
           abs(i.price - p.q50) as abs_err,
           case when i.price <> 0 then abs(i.price - p.q50)/i.price else null end as ape,
           i.ts
    from items i
    join preds p on p.item_ref = i.item_ref and p.ts::date = i.ts::date;
  else
    raise notice 'Skipping item-level backtest: item_ref not present.';
  end if;
end$$;
SQL

# 5) apply migration
echo "[apply_v0_3] applying migration…"
if [[ -n "${PSQL_DSN:-}" ]]; then
  psql "$PSQL_DSN" -v ON_ERROR_STOP=1 -f db/migrations/2025-10-17-v0.3.sql
else
  : "${SUPABASE_HOST:?SUPABASE_HOST missing}"
  : "${SUPABASE_DB:?SUPABASE_DB missing}"
  : "${SUPABASE_USER:?SUPABASE_USER missing}"
  : "${SUPABASE_PASS:?SUPABASE_PASS missing}"
  psql "sslmode=require host=$SUPABASE_HOST dbname=$SUPABASE_DB user=$SUPABASE_USER password=$SUPABASE_PASS" \
       -v ON_ERROR_STOP=1 -f db/migrations/2025-10-17-v0.3.sql
fi

# 6) refresh MV once
if [[ -n "${PSQL_DSN:-}" ]]; then
  psql "$PSQL_DSN" -v ON_ERROR_STOP=1 -f db/cron/refresh_v0_3.sql
else
  psql "sslmode=require host=$SUPABASE_HOST dbname=$SUPABASE_DB user=$SUPABASE_USER password=$SUPABASE_PASS" \
       -v ON_ERROR_STOP=1 -f db/cron/refresh_v0_3.sql
fi

# 7) run head once
echo "[apply_v0_3] running v0.3 head once…"
. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate
pip install -q -r requirements.txt
python3 heads/q50_head.py

echo "[apply_v0_3] done."
