-- Nightly catalogue prices stopped refreshing (2026-09-26).
--
-- The watchdog's one HIGH: cron job refresh-mv-catalog-item-price "failed" 4
-- of the last 14 nights, 3 in a row (09-24..26), each "canceling statement due
-- to statement timeout". The job runs under the database default of 2 min and
-- the refresh now takes 120.6 s (timed by hand 2026-09-26, succeeded with a
-- longer limit) — it grew past the limit, so catalogue prices (browse rails,
-- set pages, the catalogue item's median) froze at 09-23.
--
-- refresh-core-mvs-15m is on the same edge: 1:53 max in 14 days, one failure.
-- Each job now sets its own limit in the command; the default stays 2 min for
-- everything else. By jobname, so the job ids do not matter.
--
-- Falsifier: SELECT status FROM cron.job_run_details d JOIN cron.job j USING (jobid)
--   WHERE j.jobname = 'refresh-mv-catalog-item-price' ORDER BY start_time DESC LIMIT 1;
--   -> 'succeeded' after the next 00:00 UTC run.

SELECT cron.alter_job(
  (SELECT jobid FROM cron.job WHERE jobname = 'refresh-mv-catalog-item-price'),
  command := $cmd$SET statement_timeout = '15min'; REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_catalog_item_price$cmd$
);

SELECT cron.alter_job(
  (SELECT jobid FROM cron.job WHERE jobname = 'refresh-core-mvs-15m'),
  command := $cmd$SET statement_timeout = '10min'; select public.refresh_core_mvs();$cmd$
);
