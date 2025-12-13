-- metrics table for function runs (Cal-AI style)
create table if not exists public.fn_metrics (
  id bigserial primary key,
  fn text not null,
  status text not null,
  latency_ms integer,
  idem_key text,
  session_id uuid,
  payload jsonb,
  created_at timestamptz not null default now()
);

create index if not exists fn_metrics_fn_created_idx on public.fn_metrics (fn, created_at desc);
create index if not exists training_items_category_idx on public.training_items ((attributes->>'category'));
