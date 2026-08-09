-- rollup-price-prediction-daily: raise the per-job statement_timeout.
--
-- APPLIED LIVE via DB_DSN_DIRECT 2026-07-29 — this file is the source-of-truth
-- record (same pattern as scripts/20260712_mv_market_top_movers.sql).
--
-- The job upserts the last 2 days of price_predictions into the
-- price_prediction_daily warm tier. It was failing intermittently:
--
--   2026-07-27  failed     ERROR: canceling statement due to statement timeout
--   2026-07-28  succeeded  INSERT 0 118358
--   2026-07-29  failed     ERROR: canceling statement due to statement timeout
--
-- Measured rather than guessed: the SELECT half alone takes ~34s over 182,228
-- groups, and a full manual run takes 3m08s — against a database
-- statement_timeout of 2min. So it was never comfortably inside the ceiling;
-- it succeeded only on nights when the set happened to be small enough.
--
-- Consequence when it fails: the warm tier goes stale for that day and chart
-- reads fall back to the hot partitioned table, which is the load this rollup
-- exists to avoid.
--
-- pg_cron runs each job in its own session, so prepending SET raises the
-- ceiling for THIS job only and leaves the global 2min default intact.
--
-- Verified after applying: manual run completed INSERT 0 182228 in 3m08s,
-- which also backfilled the day the 07-29 failure dropped.

SELECT cron.alter_job(
  jobid,
  command => 'SET statement_timeout = ''10min''; ' || command
)
FROM cron.job
WHERE jobname = 'rollup-price-prediction-daily'
  AND command NOT LIKE '%statement_timeout%';
