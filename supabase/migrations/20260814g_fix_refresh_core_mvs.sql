-- refresh_core_mvs() has been a NO-OP since it was written.
--
-- It ran `REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS <name>`. There is no
-- IF EXISTS clause on REFRESH MATERIALIZED VIEW, so every call raised
-- `syntax error at or near "exists"` — and each was wrapped in
-- `exception when others then null`, which swallowed it.
--
-- The cron job fired every 15 minutes, 96 times a day, and refreshed nothing.
-- It reported success the whole time. `mv_daily_median_price` was frozen at
-- 2026-05-02 — 104 days — while its source data was current to today.
-- `mv_item_best_comp_canon` escaped only because a SEPARATE hourly job
-- refreshes it with valid syntax.
--
-- Two changes beyond the syntax:
--   * A failed refresh RAISEs a WARNING instead of vanishing. Warnings reach
--     the Postgres log, which is the layer the daily watchdog reads and the one
--     that sees what the EC2 journal cannot.
--   * Each refresh keeps its own exception block, so one failing matview cannot
--     stop the others — which is the only defensible part of the original.
CREATE OR REPLACE FUNCTION public.refresh_core_mvs()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public, pg_temp'
AS $function$
begin
  begin
    refresh materialized view concurrently public.mv_item_best_comp_canon;
  exception when others then
    raise warning 'refresh_core_mvs: mv_item_best_comp_canon failed: %', sqlerrm;
  end;

  begin
    refresh materialized view concurrently public.mv_daily_median_price;
  exception when others then
    raise warning 'refresh_core_mvs: mv_daily_median_price failed: %', sqlerrm;
  end;

  -- Per-category catalogue size, read by v_category_summaries_v1. Added
  -- 2026-08-14 when that view was timing out (57014) on Analytics.
  begin
    refresh materialized view concurrently public.mv_category_totals;
  exception when others then
    raise warning 'refresh_core_mvs: mv_category_totals failed: %', sqlerrm;
  end;
end$function$;
