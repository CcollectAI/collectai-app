create table if not exists public.market_cache (
  id bigserial primary key,
  provider text not null,
  q text not null,
  category text,
  hits jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists market_cache_q_idx on public.market_cache (provider, q, coalesce(category, ''));
-- simple per-sub per-minute token bucket
create table if not exists public.rate_limits (
  id bigserial primary key,
  subject text not null,           -- JWT sub
  resource text not null,          -- e.g., 'market-search'
  ts timestamptz not null default now()
);
create index if not exists rate_limits_subject_idx on public.rate_limits (subject, resource, ts desc);
