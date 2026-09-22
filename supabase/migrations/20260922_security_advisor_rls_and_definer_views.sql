-- 2026-09-22: Security Advisor ERRORs — 11 x rls_disabled_in_public,
-- 10 x security_definer_view (21 total). This file fixes 12 of them. The 9 left
-- over are deliberate, and are listed at the bottom so nobody re-"fixes" them.
--
-- WHAT WAS LIVE (measured 2026-09-22 against prod, not inferred):
--   Every one of the 11 tables had RLS off AND `anon` held SELECT, INSERT,
--   UPDATE, DELETE. The anon key ships in the app bundle, so anyone could
--   rewrite market_hits_daily (6.6M rows) / price_prediction_daily (4.9M),
--   which feed catalogue prices, over PostgREST. v_images_needing_embeddings
--   (DEFINER, no auth.uid() filter) handed anon every member's item_images rows.
--
-- WHY THIS IS SAFE FOR THE BACKEND:
--   The server connects as `postgres`; `postgres` and `service_role` both have
--   rolbypassrls = t. No function in `public` references the 7 tables or the
--   5 views except refresh_core_mvs, which is SECURITY DEFINER (runs as owner).
--   No `.from()` in src/, app/, supabase/functions/ or collectai-admin/src/
--   reads any of them (checked 2026-09-22). Dependent views/MVs
--   (v_new_listings_radar, v_item_best_comp_scored_v2, mv_catalog_item_price,
--   …) are likewise read by no client.
--
-- FALSIFIER: re-run the advisor lint and expect rls_disabled_in_public = the
--   4 ugc_* tables only, and security_definer_view = the 5 views in section 3
--   only. Then, as anon:
--     SET ROLE anon; SELECT 1 FROM public.market_hits_daily LIMIT 1;
--   must ERROR with "permission denied".

SET lock_timeout = '5s';

-- 1. Backend-only tables: RLS on (no policy = deny for anon/authenticated),
--    and revoke the grants so PostgREST roles cannot reach them at all.
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'market_hits_daily',                    -- rollup behind catalogue prices
    'price_prediction_daily',               -- warm-tier chart history
    'model_promotion_log',                  -- model_retrain_worker audit trail
    'vision_category_quality',              -- vision_quality_worker
    'vision_category_regret',               -- vision_regret_worker
    '_cat_sum_before',                      -- one-off snapshot table
    'jsonb_double_encode_backup_20260823'   -- one-off backup table
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
  END LOOP;
END $$;

-- 2. Backend-only DEFINER views: run as the caller, and not reachable by
--    PostgREST roles at all.
DO $$
DECLARE
  v text;
BEGIN
  FOREACH v IN ARRAY ARRAY[
    'v_images_needing_embeddings',   -- joined every member's item_images, unfiltered
    'v_item_best_comp_full',
    'v_market_hits_canon',
    'v_category_comp_coverage',
    'v_category_comp_coverage_canon'
  ] LOOP
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = true)', v);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', v);
  END LOOP;
END $$;

-- 3. DELIBERATELY NOT CHANGED — the advisor will keep flagging these.
--
--   DEFINER by design. Flipping them to invoker OPENS privacy gates or empties
--   the screen; see 20260804_privacy_settings_enforcement.sql:29-35 and
--   scripts/check-view-rls.mjs (house pattern: DEFINER + auth.uid()):
--     user_public_profile_v1, user_public_profiles   privacy-gated public profiles
--     v_chat_inbox_v1                                 WHERE p.user_id = auth.uid()
--     v_item_values_v1                                WHERE i.user_id = auth.uid()
--     v_category_summaries_v1                         filters on auth.uid()
--
--   RLS still OFF, pending a decision: ugc_tiktok_metrics, ugc_video_scripts,
--   ugc_video_audio, ugc_video_learning. collectai-admin reads/writes the first
--   two from the BROWSER with the anon key (IntelligenceTab.tsx:139,182,
--   tiktok-metrics.ts:165) behind a client-side PIN only. Denying anon breaks
--   that dashboard. The sibling ugc_* tables "have RLS", but with
--   `USING (true)` for public, which is no protection either. The real fix is
--   moving admin reads behind the service-role route handlers (adminAuth.ts).

RESET lock_timeout;
