create table if not exists public.market_observations (
  id bigserial primary key,
  provider text not null,                -- 'ebay', 'reddit', 'discogs', etc.
  source_id text not null,               -- provider’s listing/thread id
  url text,
  title text,
  category text,
  condition text,
  currency text,
  price numeric,                         -- as reported
  price_eur numeric,                     -- normalized
  is_sold boolean not null default false,
  observed_at timestamptz not null,      -- listing/sold time
  image_url text,
  raw jsonb,
  created_at timestamptz not null default now(),
  unique(provider, source_id)
);

create index if not exists market_obs_cat_time on public.market_observations (category, observed_at desc);
create index if not exists market_obs_sold_time on public.market_observations (is_sold, observed_at desc);
