-- Reconcile public.user_feedback_events_v1 to the schema the writer
-- (feedback_router.submit_feedback) and readers (pipelines/export_feedback.py,
-- pipelines/train_price.py) expect: feedback_type + value_json + incorporated_at.
--
-- Why: the live table had diverged to an event_type/payload/status shape
-- (created outside 20260202) that matched NEITHER the readers NOR the repo
-- migrations, and the writer was inserting into the unrelated ML `feedback`
-- table entirely — so every POST /feedback/submit 500'd and the training
-- feedback loop had zero fuel. The table is empty (0 rows), so these additive
-- changes are safe. See 20260202_ingest_pipeline_tables.sql (original intent)
-- and 20260210_evidence_native.sql (incorporated_at).
--
-- feedback_type is intentionally left un-CHECKed: the app also submits
-- 'disagree' / 'accurate' qualitative signals which are NOT training price
-- types. The readers filter feedback_type IN ('sale_price','price_correction',
-- 'verified_sale'), so non-price rows are naturally ignored by training.

ALTER TABLE public.user_feedback_events_v1
  ADD COLUMN IF NOT EXISTS feedback_type       TEXT,
  ADD COLUMN IF NOT EXISTS value_json          JSONB,
  ADD COLUMN IF NOT EXISTS source              TEXT DEFAULT 'app',
  ADD COLUMN IF NOT EXISTS incorporated_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS incorporated_run_id TEXT;

CREATE INDEX IF NOT EXISTS idx_user_feedback_type
  ON public.user_feedback_events_v1 (feedback_type);

-- The divergent NOT NULL columns (event_type / payload / status), if present on
-- this database, must not block writes that only populate the canonical feedback
-- columns. Give them defaults. Guarded so this migration is also valid on a
-- fresh DB built purely from the repo (where these columns don't exist).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'user_feedback_events_v1'
               AND column_name = 'event_type') THEN
    ALTER TABLE public.user_feedback_events_v1 ALTER COLUMN event_type SET DEFAULT 'price_feedback';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'user_feedback_events_v1'
               AND column_name = 'payload') THEN
    ALTER TABLE public.user_feedback_events_v1 ALTER COLUMN payload SET DEFAULT '{}'::jsonb;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'user_feedback_events_v1'
               AND column_name = 'status') THEN
    ALTER TABLE public.user_feedback_events_v1 ALTER COLUMN status SET DEFAULT 'new';
  END IF;
END $$;
