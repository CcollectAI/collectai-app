-- Create buckets (idempotent). RLS on storage.objects is already enabled by default in Supabase.
insert into storage.buckets (id, name, public) values
  ('captures','captures', false),
  ('processed','processed', false),
  ('refs','refs', true)
on conflict (id) do nothing;
