-- 2026-04-24: partition price_history by as_of (monthly).
-- Continuation of Week-3 deliverable from DATA_SCALING_PLAN.md §5.
-- 554k rows, all in 2026-04 (table is young). Same pattern as
-- price_predictions migration earlier today.
--
-- Choice of partition key: `as_of` is NOT NULL (enforced); `snapshot_at`
-- is nullable. Partition keys must be NOT NULL-capable. Both columns
-- carry the same semantic time axis.

BEGIN;

-- Rename existing + free up constraint/index names
ALTER TABLE public.price_history RENAME TO price_history_legacy;
ALTER TABLE public.price_history_legacy
  RENAME CONSTRAINT price_history_pkey TO price_history_legacy_pkey;

-- FK: price_history_item_id_fkey references items(id). Drop it from the
-- legacy table; we'll recreate on the partitioned parent.
ALTER TABLE public.price_history_legacy
  DROP CONSTRAINT IF EXISTS price_history_item_id_fkey;

DO $$
DECLARE idx record;
BEGIN
  FOR idx IN SELECT indexname FROM pg_indexes
             WHERE schemaname='public' AND tablename='price_history_legacy'
               AND indexname NOT LIKE '%_legacy'
  LOOP
    EXECUTE format('ALTER INDEX public.%I RENAME TO %I',
                   idx.indexname, idx.indexname || '_legacy');
  END LOOP;
END $$;

-- Partitioned parent. Keep bigint identity PK (id, as_of) composite.
-- Triggers on partitioned tables propagate to all partitions in PG13+.
CREATE TABLE public.price_history (
    id          bigint GENERATED ALWAYS AS IDENTITY,
    item_id     uuid,
    source      text NOT NULL,
    price       numeric(12,2),
    currency    text DEFAULT 'EUR',
    as_of       timestamptz NOT NULL DEFAULT now(),
    item_ref    text,
    price_q10   numeric,
    price_q50   numeric,
    price_q90   numeric,
    snapshot_at timestamptz DEFAULT now(),
    CONSTRAINT price_history_pkey PRIMARY KEY (id, as_of),
    CONSTRAINT price_history_item_id_fkey FOREIGN KEY (item_id)
      REFERENCES public.items(id) ON DELETE CASCADE
) PARTITION BY RANGE (as_of);

-- Partitions. Existing data lives in 2026-04 only; 3 months future runway.
CREATE TABLE public.price_history_y2026m04 PARTITION OF public.price_history
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE public.price_history_y2026m05 PARTITION OF public.price_history
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE public.price_history_y2026m06 PARTITION OF public.price_history
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE public.price_history_y2026m07 PARTITION OF public.price_history
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE public.price_history_default PARTITION OF public.price_history DEFAULT;

-- Backfill. The identity column keeps generating new ids on INSERT, so
-- we must explicitly override system values to preserve the existing ids.
INSERT INTO public.price_history
  OVERRIDING SYSTEM VALUE
  SELECT id, item_id, source, price, currency, as_of, item_ref,
         price_q10, price_q50, price_q90, snapshot_at
  FROM public.price_history_legacy;

-- Advance identity sequence past the imported max(id) so future inserts
-- don't collide.
SELECT setval(
  pg_get_serial_sequence('public.price_history', 'id'),
  COALESCE((SELECT MAX(id) FROM public.price_history), 0) + 1,
  false
);

-- Indexes (propagate to all partitions)
CREATE INDEX idx_price_history_item_ref_snapshot ON public.price_history (item_ref, snapshot_at DESC) WHERE item_ref IS NOT NULL;
CREATE INDEX idx_price_history_item_time         ON public.price_history (item_id, as_of DESC);

-- RLS + owner-scoped policies (match legacy)
ALTER TABLE public.price_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "price_history select owner items" ON public.price_history
  FOR SELECT USING (EXISTS (
    SELECT 1 FROM public.items i
    WHERE i.id = price_history.item_id AND i.owner = auth.uid()
  ));
CREATE POLICY "price_history insert owner items" ON public.price_history
  FOR INSERT WITH CHECK (EXISTS (
    SELECT 1 FROM public.items i
    WHERE i.id = price_history.item_id AND i.owner = auth.uid()
  ));

-- pg_cron helper function, parallel to market_hits + price_predictions ones.
CREATE OR REPLACE FUNCTION public.ensure_next_month_price_history_partition()
RETURNS void
LANGUAGE plpgsql
SET search_path TO 'public, pg_temp'
AS $$
DECLARE
  next_start date := date_trunc('month', now()::date + interval '1 month')::date;
  part_after date := (next_start + interval '1 month')::date;
  part_name  text := format('price_history_y%sm%s',
                            to_char(next_start, 'YYYY'),
                            to_char(next_start, 'MM'));
  exists_already bool;
BEGIN
  SELECT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) INTO exists_already;
  IF NOT exists_already THEN
    EXECUTE format(
      'CREATE TABLE public.%I PARTITION OF public.price_history FOR VALUES FROM (%L) TO (%L)',
      part_name, next_start, part_after
    );
    RAISE NOTICE 'Created partition %', part_name;
  END IF;
END $$;

COMMIT;

-- Extend pg_cron job id=32 to cover all three tables.
SELECT cron.alter_job(
  job_id := 32,
  command := $cmd$
    SELECT public.ensure_next_month_market_hits_partition();
    SELECT public.ensure_next_month_price_predictions_partition();
    SELECT public.ensure_next_month_price_history_partition();
  $cmd$
);

ANALYZE public.price_history;
