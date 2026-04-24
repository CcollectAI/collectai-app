-- 2026-04-24: drop 8 overbroad RLS policies flagged by Supabase advisor
-- (rule: rls_policy_always_true). Each has USING and/or WITH CHECK = true
-- for UPDATE/DELETE/INSERT/ALL applied to anon/authenticated/public role,
-- effectively bypassing row-level security.
--
-- Safe to drop: (a) none read by the frontend via .from() (grep verified),
-- (b) tables keep their proper owner-scoped policies + service-role bypass.

DROP POLICY IF EXISTS admin_content_config_all                 ON public.admin_content_config;
DROP POLICY IF EXISTS admin_dev_hub_all                        ON public.admin_dev_hub;
DROP POLICY IF EXISTS "Allow all operations on image_embeddings" ON public.image_embeddings;
DROP POLICY IF EXISTS own_item_embeddings                      ON public.item_embeddings;
DROP POLICY IF EXISTS label_events_delete_auth                 ON public.label_events;
DROP POLICY IF EXISTS label_events_update_auth                 ON public.label_events;
DROP POLICY IF EXISTS "Allow all operations on model_registry" ON public.model_registry;
DROP POLICY IF EXISTS "Allow all operations on model_runs"     ON public.model_runs;
