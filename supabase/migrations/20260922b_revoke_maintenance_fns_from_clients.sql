-- 2026-09-22: six maintenance functions were callable by ANYONE with the anon key.
--
-- All six are SECURITY DEFINER (run as postgres, bypass RLS) and carried the
-- Postgres default ACL `=X/postgres` — EXECUTE for PUBLIC. anon and
-- authenticated inherit PUBLIC, so revoking from them alone changes nothing;
-- PUBLIC must be revoked too.
--
-- Worst of them: `POST /rest/v1/rpc/cleanup_market_hits {"p_days":0}` ran
-- `DELETE FROM market_hits WHERE ... < now()` — the whole pricing dataset.
-- refresh_core_mvs / refresh_* let any caller force back-to-back
-- REFRESH MATERIALIZED VIEW CONCURRENTLY runs (load on a Small instance).
--
-- Callers (checked 2026-09-22): pg_cron only — job 18 refresh_core_mvs and
-- job 27 cleanup_market_hits(365), both username=postgres, the owner, which
-- keeps EXECUTE. No `.rpc()` in src/, app/, supabase/functions/ or
-- collectai-admin/src/, and no reference under server/ names any of the six.
--
-- FALSIFIER: as anon, `SELECT public.refresh_core_mvs();` must ERROR with
-- "permission denied for function"; `SELECT proacl FROM pg_proc WHERE
-- proname = 'refresh_core_mvs'` must show no leading `=X` and no anon/
-- authenticated entry.
--
-- The wider class — 150 SECURITY DEFINER functions in public, all executable
-- by anon through the same PUBLIC default — is NOT swept here. Most are real
-- client RPCs. See docs/CLASS_SWEEPS.md.

REVOKE EXECUTE ON FUNCTION
  public.cleanup_market_hits(integer),
  public.cleanup_old_tasks(),
  public.cleanup_stale_presence(),
  public.refresh_category_summaries(),
  public.refresh_core_mvs(),
  public.refresh_mv_top_movers()
FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION
  public.cleanup_market_hits(integer),
  public.cleanup_old_tasks(),
  public.cleanup_stale_presence(),
  public.refresh_category_summaries(),
  public.refresh_core_mvs(),
  public.refresh_mv_top_movers()
TO service_role;
