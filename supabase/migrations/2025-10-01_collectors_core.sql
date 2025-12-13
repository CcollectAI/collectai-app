-- Core tables for Collectors Merge
-- Safe: create if not exists patterns

create table if not exists public.items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  category text not null,
  normalized_key text,
  title text,
  condition text,
  grade text,
  graded_by text,
  sealed boolean,
  attributes_json jsonb default '{}'::jsonb,
  images jsonb default '[]'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_items_user on public.items(user_id);
create index if not exists idx_items_category on public.items(category);
create index if not exists idx_items_normalized_key on public.items(normalized_key);

create table if not exists public.market_hits (
  id bigserial primary key,
  provider text not null,
  listing_id text not null,
  title text,
  price numeric(12,2),
  currency text,
  shipping numeric(12,2),
  condition text,
  graded boolean,
  ended_at timestamptz,
  url text,
  seller_score numeric(6,2),
  features_json jsonb default '{}'::jsonb,
  normalized_key text,
  created_at timestamptz default now()
);

create index if not exists idx_mh_provider_listing on public.market_hits(provider, listing_id);
create index if not exists idx_mh_ended_at on public.market_hits(ended_at);
create index if not exists idx_mh_normkey on public.market_hits(normalized_key);

create table if not exists public.price_predictions (
  id bigserial primary key,
  item_id uuid references public.items(id) on delete cascade,
  model_version text not null,
  y_hat numeric(12,2),
  q10 numeric(12,2),
  q50 numeric(12,2),
  q90 numeric(12,2),
  conf_score numeric(5,2),
  features_used jsonb,
  asof timestamptz default now()
);
create index if not exists idx_pp_item_asof on public.price_predictions(item_id, asof desc);

create table if not exists public.models (
  id bigserial primary key,
  category text not null,
  version text not null,
  train_window text,
  featureset_hash text,
  metrics_json jsonb,
  created_at timestamptz default now(),
  unique(category, version)
);

create table if not exists public.feedback (
  id bigserial primary key,
  item_id uuid references public.items(id) on delete cascade,
  label text, -- e.g., "sale_price:123.45" or "disagree:too_high"
  observed_at timestamptz default now()
);
create index if not exists idx_feedback_item on public.feedback(item_id);

-- Watchlist & events
create table if not exists public.watchlist (
  id bigserial primary key,
  user_id uuid not null,
  normalized_key text not null,
  created_at timestamptz default now(),
  unique(user_id, normalized_key)
);

create table if not exists public.events (
  id bigserial primary key,
  item_id uuid references public.items(id) on delete cascade,
  kind text not null, -- "provenance:add_receipt", "ownership:transfer", "grading:psa10"
  payload jsonb not null,
  created_at timestamptz default now()
);
create index if not exists idx_events_item on public.events(item_id, created_at desc);
create table if not exists public.alert_rules (
  id bigserial primary key,
  user_id uuid not null,
  normalized_key text,
  category text,
  spike_pct numeric(5,2) default 15.0, -- p7 >= (1+spike_pct%) * p30
  drop_pct numeric(5,2) default 15.0,  -- p7 <= (1-drop_pct%) * p30
  enabled boolean default true,
  created_at timestamptz default now(),
  unique(user_id, coalesce(normalized_key,''), coalesce(category,''))
);

alter table public.alert_rules enable row level security;

create policy if not exists alert_rules_owner_select on public.alert_rules
for select using (auth.uid() = user_id);
create policy if not exists alert_rules_owner_mod on public.alert_rules
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
