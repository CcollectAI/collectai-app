-- 20260212_alert_history_batch_index.sql
-- Optimal composite index for the batched alerts_worker query.
--
-- The alerts_worker NOT EXISTS subquery filters on:
--   (user_id, item_id, trigger_type, created_at DESC)
--
-- This 4-column index covers the subquery exactly, avoiding per-row seq scans
-- on alert_trigger_history during the batch check.
--
-- Uses CONCURRENTLY to avoid locking the table during creation.
-- Note: CONCURRENTLY cannot run inside a transaction block — run this
-- migration outside of a multi-statement transaction if needed.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_history_user_item_type_created
    ON public.alert_trigger_history (user_id, item_id, trigger_type, created_at DESC);
