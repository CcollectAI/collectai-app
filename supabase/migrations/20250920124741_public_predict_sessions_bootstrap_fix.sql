do $outer$
begin
  -- Enable pgcrypto for gen_random_uuid
  create extension if not exists pgcrypto;

  -- Create table if missing
  if to_regclass('public.predict_sessions') is null then
    create table public.predict_sessions (
      id              bigserial primary key,
      uuid_id         uuid default gen_random_uuid(),
      user_id         uuid,
      item_id         bigint,
      category        text not null,
      status          text not null default 'pending',
      confidence      numeric(5,2),
      price_low_eur   numeric(12,2),
      price_mid_eur   numeric(12,2),
      price_high_eur  numeric(12,2),
      features        jsonb,
      comps           jsonb,
      created_at      timestamptz not null default now(),
      updated_at      timestamptz not null default now()
    );
  end if;

  -- Idempotent column defaults (ignore if column not present etc.)
  begin
    alter table public.predict_sessions
      alter column uuid_id set default gen_random_uuid();
  exception when others then null; end;

  -- Ensure uuid_id can be NULL initially (we’ll backfill separately if needed)
  begin
    alter table public.predict_sessions
      alter column uuid_id drop not null;
  exception when others then null; end;

  -- Unique index on uuid_id
  create unique index if not exists predict_sessions_uuid_id_key
    on public.predict_sessions(uuid_id);

  -- Touch-updated_at trigger function (idempotent create/replace)
  create or replace function public.trg_touch_updated_at()
  returns trigger language plpgsql as $f$
  begin
    new.updated_at := now();
    return new;
  end
  $f$;

  -- Create trigger if not exists
  if not exists (
    select 1 from pg_trigger
    where tgname = 'predict_sessions_touch_updated_at'
  ) then
    create trigger predict_sessions_touch_updated_at
      before update on public.predict_sessions
      for each row execute function public.trg_touch_updated_at();
  end if;

  -- RLS: owner-only
  alter table public.predict_sessions enable row level security;

  -- Drop old policies if any
  begin
    drop policy if exists predict_sessions_select_own on public.predict_sessions;
    drop policy if exists predict_sessions_insert_own on public.predict_sessions;
    drop policy if exists predict_sessions_update_own on public.predict_sessions;
  exception when others then null; end;

  create policy predict_sessions_select_own
    on public.predict_sessions
    for select to authenticated
    using (user_id = auth.uid());

  create policy predict_sessions_insert_own
    on public.predict_sessions
    for insert to authenticated
    with check (user_id = auth.uid());

  create policy predict_sessions_update_own
    on public.predict_sessions
    for update to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

  grant select on public.predict_sessions to authenticated;

  -- Reload PostgREST cache
  perform pg_notify('pgrst','reload schema');

end
$outer$;
