create table if not exists items (
  id bigserial primary key,
  s3_key text unique,
  category text,
  label text,
  created_at timestamptz default now()
);

create table if not exists price_predictions (
  id bigserial primary key,
  item_ref text,
  category text,
  model_version text,
  q10 numeric,
  q50 numeric,
  q90 numeric,
  confidence numeric,
  raw jsonb,
  created_at timestamptz default now()
);
create index if not exists pp_item_ref_idx on price_predictions(item_ref);
create index if not exists pp_category_idx on price_predictions(category);
create index if not exists pp_created_idx on price_predictions(created_at);

create table if not exists market_hits (
  id bigserial primary key,
  item_ref text,
  category text,
  price numeric,
  currency text,
  source text,
  observed_at timestamptz,
  raw jsonb,
  created_at timestamptz default now()
);
create index if not exists mh_item_ref_idx on market_hits(item_ref);
create index if not exists mh_category_idx on market_hits(category);
create index if not exists mh_observed_idx on market_hits(observed_at);

create table if not exists model_metrics (
  id bigserial primary key,
  model_version text,
  category text,
  mae numeric,
  mape numeric,
  n int,
  window text,
  computed_at timestamptz default now()
);
create index if not exists mm_model_cat_idx on model_metrics(model_version, category, computed_at);
