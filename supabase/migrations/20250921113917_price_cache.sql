create table if not exists public.price_cache (
  id bigserial primary key,
  keyhash text not null,            -- hash of (title,category,condition)
  price_eur numeric not null,
  created_at timestamptz not null default now()
);
create index if not exists price_cache_key_idx on public.price_cache (keyhash, created_at desc);
-- rate_limits already exists from market-search; if not, create minimal
create table if not exists public.rate_limits (
  id bigserial primary key,
  subject text not null,
  resource text not null,
  ts timestamptz not null default now()
);
create index if not exists rate_limits_subject_idx on public.rate_limits (subject, resource, ts desc);
