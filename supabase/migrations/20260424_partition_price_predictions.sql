-- 2026-04-24: partition price_predictions by generated_at (monthly).
-- Week-3 deliverable from DATA_SCALING_PLAN.md §5. 550k rows, range
-- 2025-11 → 2026-04 (6 months). Same pattern as the market_hits
-- partitioning landed in R50m.
--
-- Strategy:
--   1. Rename existing table → price_predictions_legacy
--   2. Create partitioned parent (same schema, composite PK)
--   3. Create 2025-11 through 2026-09 partitions + default catch-all
--   4. Backfill via INSERT ... SELECT
--   5. Recreate indexes (Postgres creates per-partition indexes from
--      a partitioned-index definition on the parent)
--   6. Recreate the Class B deny-all policy
--   7. Legacy table keeps data for rollback; dropped in a follow-up once
--      workers have confirmed clean writes
--
-- Bake must be stopped during this migration. Valuation_worker writes to
-- price_predictions continuously; concurrent writes during rename fail
-- with relation-missing. Caller script stops bake, runs, then starts bake.

BEGIN;

-- Rename existing -> legacy. Renaming a table does NOT rename its
-- constraints or indexes, so we also rename the PK + CHECK constraint
-- and the named indexes to free up the names for the partitioned parent.
ALTER TABLE public.price_predictions RENAME TO price_predictions_legacy;
ALTER TABLE public.price_predictions_legacy
  RENAME CONSTRAINT price_predictions_pkey   TO price_predictions_legacy_pkey;
ALTER TABLE public.price_predictions_legacy
  RENAME CONSTRAINT price_predictions_sanity TO price_predictions_legacy_sanity;

-- Rename indexes to avoid collision with the partitioned-parent index names
DO $$
DECLARE
  idx record;
BEGIN
  FOR idx IN
    SELECT indexname FROM pg_indexes
    WHERE schemaname='public' AND tablename='price_predictions_legacy'
      AND indexname NOT LIKE '%_legacy'
  LOOP
    EXECUTE format('ALTER INDEX public.%I RENAME TO %I',
                   idx.indexname, idx.indexname || '_legacy');
  END LOOP;
END $$;

-- Create partitioned parent. generated_at is part of composite PK so
-- partition pruning works at read time. Postgres requires the partition
-- key to be in any unique constraint.
CREATE TABLE public.price_predictions (
    id                 uuid NOT NULL DEFAULT gen_random_uuid(),
    nk                 text NOT NULL DEFAULT gen_random_uuid()::text,
    q10                numeric,
    q50                numeric,
    q90                numeric,
    confidence         numeric,
    comps_count        integer,
    model_version      text,
    source             text,
    training_data_asof timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    item_ref           text,
    category           text,
    raw                jsonb,
    ts                 timestamptz NOT NULL DEFAULT now(),
    head               text,
    generated_at       timestamptz NOT NULL DEFAULT now(),
    evidence_hit_ids   text[] DEFAULT '{}'::text[],
    evidence_summary   jsonb  DEFAULT '{}'::jsonb,
    explanation        text,
    conf_score         numeric,
    CONSTRAINT price_predictions_pkey PRIMARY KEY (id, generated_at),
    CONSTRAINT price_predictions_sanity CHECK (
        (q10 IS NULL OR q10 >= 0) AND
        (q50 IS NULL OR q50 >= 0) AND
        (q90 IS NULL OR q90 >= 0) AND
        (q10 IS NULL OR q90 IS NULL OR q10 <= q90) AND
        (q10 IS NULL OR q50 IS NULL OR q10 <= q50) AND
        (q50 IS NULL OR q90 IS NULL OR q50 <= q90) AND
        (q90 IS NULL OR q90 <= 20000000)
    )
) PARTITION BY RANGE (generated_at);

-- Monthly partitions covering data + 3 months future runway.
-- Default catch-all (below) handles any straggler outside range.
CREATE TABLE public.price_predictions_y2025m11 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE public.price_predictions_y2025m12 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
CREATE TABLE public.price_predictions_y2026m01 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE public.price_predictions_y2026m02 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE public.price_predictions_y2026m03 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE public.price_predictions_y2026m04 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE public.price_predictions_y2026m05 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE public.price_predictions_y2026m06 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE public.price_predictions_y2026m07 PARTITION OF public.price_predictions
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE public.price_predictions_default PARTITION OF public.price_predictions DEFAULT;

-- Backfill from legacy. 550k rows, expect ~30-60s.
INSERT INTO public.price_predictions
  SELECT * FROM public.price_predictions_legacy;

-- Recreate indexes (minus the duplicates + INVALID one). Indexes on
-- partitioned parent propagate to all partitions automatically.
CREATE INDEX idx_pp_nk_created                   ON public.price_predictions (nk, created_at DESC);
CREATE INDEX idx_price_predictions_cat_head_ts   ON public.price_predictions (category, head, ts DESC);
CREATE INDEX idx_price_predictions_category_gen  ON public.price_predictions (category, generated_at DESC) WHERE category IS NOT NULL;
CREATE INDEX pp_category_idx                     ON public.price_predictions (category);
CREATE INDEX pp_item_ref_idx                     ON public.price_predictions (item_ref);
CREATE INDEX pp_model_idx                        ON public.price_predictions (model_version);
CREATE INDEX pp_created_idx                      ON public.price_predictions (created_at);

-- Re-enable RLS + deny-all (from the Class B bulk earlier today).
ALTER TABLE public.price_predictions ENABLE ROW LEVEL SECURITY;
CREATE POLICY price_predictions_deny_all ON public.price_predictions
  FOR ALL USING (false) WITH CHECK (false);

-- pg_cron: ensure-next-month function, parallel to the one for market_hits.
CREATE OR REPLACE FUNCTION public.ensure_next_month_price_predictions_partition()
RETURNS void
LANGUAGE plpgsql
SET search_path TO 'public, pg_temp'
AS $$
DECLARE
  next_start date := date_trunc('month', now()::date + interval '1 month')::date;
  part_after date := (next_start + interval '1 month')::date;
  part_name  text := format('price_predictions_y%sm%s',
                            to_char(next_start, 'YYYY'),
                            to_char(next_start, 'MM'));
  exists_already bool;
BEGIN
  SELECT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) INTO exists_already;
  IF NOT exists_already THEN
    EXECUTE format(
      'CREATE TABLE public.%I PARTITION OF public.price_predictions FOR VALUES FROM (%L) TO (%L)',
      part_name, next_start, part_after
    );
    RAISE NOTICE 'Created partition %', part_name;
  END IF;
END $$;

COMMIT;

-- Update pg_cron job id=32 to also create price_predictions partitions.
-- (Done outside the transaction because cron.alter_job uses a separate
-- transaction.)
SELECT cron.alter_job(
  job_id := 32,
  command := $cmd$
    SELECT public.ensure_next_month_market_hits_partition();
    SELECT public.ensure_next_month_price_predictions_partition();
  $cmd$
);

ANALYZE public.price_predictions;
