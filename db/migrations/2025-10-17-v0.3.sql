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
