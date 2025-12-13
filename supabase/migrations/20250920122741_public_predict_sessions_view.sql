do $$
begin
  if to_regclass('predictive_capture.sessions') is null then
    raise notice 'predictive_capture.sessions not found; skipping view create';
    return;
  end if;

  -- Updatable view: simple 1:1 mapping, so INSERT/UPDATE/DELETE work through it.
  create or replace view public.predict_sessions as
  select
    id, uuid_id, user_id, item_id, category, status, confidence,
    price_low_eur, price_mid_eur, price_high_eur, features, comps,
    created_at, updated_at
  from predictive_capture.sessions;

  comment on view public.predict_sessions is
    'Updatable view over predictive_capture.sessions so API/functions can use the public schema';

  -- Ensure base table uses RLS; view inherits base table RLS behavior at execution
  alter table predictive_capture.sessions enable row level security;

  -- Allow authenticated clients to SELECT the view (writes handled by functions w/ service key)
  grant select on public.predict_sessions to authenticated;

  -- Nudge PostgREST cache (ignore errors)
  perform pg_notify('pgrst','reload schema');
exception when others then
  raise;
end $$;
