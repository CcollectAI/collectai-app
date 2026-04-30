-- 2026-05-01 perf fixes from EXPLAIN ANALYZE diagnosis on production:
--
-- Task #24 (notif_history unread_count): EXPLAIN showed 124ms execution + slow
-- planning on a 5-row table; the partial index idx_notification_history_user_unread
-- already exists. Refresh stats so the planner uses it predictably.
--
-- Task #25 (category_items title ILIKE): EXPLAIN timed out at 30s on the
-- 140k-row table. No trigram index on title. Add gin (title gin_trgm_ops);
-- pg_trgm is already installed.
--
-- Task #24 + #26 also benefit from refreshed pg_class/pg_statistic — the
-- 6.7s planning time on portfolio_cat_breakdown and the slow notif_history
-- planning both look like stale-stats symptoms.
--
-- This migration is idempotent. ANALYZE always works. CREATE INDEX
-- IF NOT EXISTS CONCURRENTLY skips if already present.

-- ---------------------------------------------------------------------------
-- #25: trigram index for category_items.title (140k rows, used by
--       /search/unified > category_items branch).
-- ---------------------------------------------------------------------------
-- pg_trgm is verified installed (perf_diag3 output 2026-05-01).
-- CREATE INDEX CONCURRENTLY can't run inside a transaction; this migration
-- file is intended to be applied via psql -f or via a Python wrapper that
-- splits on ; and runs each statement in autocommit (the apply_perf_fix.py
-- companion script does that).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_category_items_title_trgm
    ON public.category_items USING gin (title gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- #24 + #26: refresh planner stats for the affected tables.
-- ANALYZE runs synchronously and is fast on these table sizes.
-- ---------------------------------------------------------------------------
ANALYZE public.notification_history;
ANALYZE public.items;
ANALYZE public.category_items;
ANALYZE public.events;
-- price_predictions is partitioned; ANALYZE the parent + each leaf partition.
ANALYZE public.price_predictions;
