create table if not exists public.webhook_outbox (
  id bigserial primary key,
  endpoint text not null,
  payload jsonb not null,
  status text not null default 'pending',
  attempts int not null default 0,
  last_error text,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create index if not exists idx_webhook_outbox_status on public.webhook_outbox(status);
