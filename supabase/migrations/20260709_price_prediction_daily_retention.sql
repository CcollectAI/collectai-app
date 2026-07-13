-- price_prediction_daily retention (2026-07-09)
--
-- WHY: price_prediction_daily is the Phase-1 compact rollup of price_predictions
-- (one row per item_ref per day). It had NO retention and grew unbounded
-- (~1.14 GB / 4.2M rows / 69 days at creation, ~61k rows/day). It is the one
-- component of the data-tiering process (DATA_SCALING_PLAN.md §5) with no drop
-- mechanism, so it slowly eroded the headroom the partition_drop_worker frees.
--
-- SAFE: nothing in the app reads price_prediction_daily yet (write-only rollup;
-- the warm-tier read path is not wired), and older history is re-derivable from
-- the S3 Parquet lake via DuckDB. 180 days is 2x the FE's max known lookback
-- (~90d top-movers) with margin. Bump to 365 if you later want year-over-year
-- charts (caps the table at ~6 GB instead of ~3 GB).
--
-- Idempotent: cron.schedule() upserts by job name. Runs daily 03:40 (no collision
-- with existing 03:xx jobs). Deletes 0 rows until data ages past 180 days.
-- Deployed live to Supabase as cron jobid 36 on 2026-07-09.

SELECT cron.schedule(
  'price-prediction-daily-retention',
  '40 3 * * *',
  $$DELETE FROM price_prediction_daily WHERE day < (current_date - interval '180 days')$$
);
