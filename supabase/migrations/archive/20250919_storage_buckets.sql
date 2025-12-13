-- Create buckets (RLS on storage.objects is already enabled by default)
insert into storage.buckets (id, name, public) values
  ('captures','captures', false),
  ('processed','processed', false),
  ('refs','refs', true)
on conflict (id) do nothing;

-- NOTE: Do NOT ALTER storage.objects here (requires table owner).
-- Add policies via Dashboard UI (Storage → Buckets → Policies) or run owner-privileged SQL.
