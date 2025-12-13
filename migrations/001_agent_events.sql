create table if not exists agent_events (
  id bigint generated always as identity primary key,
  payload jsonb not null,
  created_at timestamptz default now()
);
