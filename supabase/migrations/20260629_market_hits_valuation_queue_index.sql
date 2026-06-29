-- Partial index for valuation_worker's "unprocessed queue" fetch.
--
-- Problem (2026-06-29): valuation_worker.py's line-232 SELECT did a parallel
-- seq scan of the m05+m06 partitions (2.3GB+1.7GB) + a sort over ~320k rows on
-- every cycle. On the pooler (30s cap) it intermittently died with
-- QueryCanceledError; when it survived, processing the whole ~580k-row /
-- ~32k-item_ref backlog blew past the 1800s bake cycle timeout. Flapping.
--
-- Fix: a partial index whose predicate MIRRORS the eligible-rows filter, so
-- only the ~59k eligible rows are indexed (not all 580k processed=false rows).
-- The worker query becomes a Merge-Append index scan ordered by item_ref with
-- a LIMIT short-circuit (~0.2s for 30k rows). Index is tiny (~2.5MB).
--
-- NOTE ON PROD APPLICATION: market_hits is partitioned, so this was applied to
-- the live DB as CREATE INDEX CONCURRENTLY on each child partition + parent
-- "CREATE INDEX ON ONLY" + "ALTER INDEX ... ATTACH PARTITION" (no write lock),
-- with SET statement_timeout=0. This file is the declarative equivalent for
-- fresh/dev DBs; on the partitioned parent Postgres auto-creates the index on
-- every existing AND future partition (so pg_cron's next-month partitions
-- inherit it automatically). CONCURRENTLY cannot run inside a migration's
-- transaction, hence the plain form here.

CREATE INDEX IF NOT EXISTS idx_market_hits_valuation_queue
    ON public.market_hits (item_ref, seen_at)
    WHERE processed = false
      AND is_listing IS NOT TRUE
      AND price IS NOT NULL
      AND item_ref IS NOT NULL;
