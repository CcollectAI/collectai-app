-- Ingest Pipeline Tables
-- Supports nightly ingest + dataset growth with taxonomy versioning
-- Created: 2026-02-02

-- ============================================================================
-- Table: ingest_runs_v1
-- Tracks each pipeline run for debugging and monitoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ingest_runs_v1 (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),

    -- Counts
    input_count INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    config_json JSONB DEFAULT '{}'::JSONB,
    errors_json JSONB DEFAULT '[]'::JSONB,
    s3_bundle_key TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingest_runs_started ON public.ingest_runs_v1 (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_status ON public.ingest_runs_v1 (status);

-- ============================================================================
-- Table: raw_observation_pointers_v1
-- Pointers to raw data in S3 + taxonomy mapping
-- Raw data is immutable; if taxonomy changes, re-run mapping
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.raw_observation_pointers_v1 (
    observation_id TEXT PRIMARY KEY,
    s3_key TEXT,                          -- Path to raw bundle in S3
    source TEXT NOT NULL,                 -- 'ebay', 'reddit', 'app_feedback', etc.
    observed_at TIMESTAMPTZ,

    -- Taxonomy mapping (can be remapped later)
    taxonomy_version TEXT NOT NULL DEFAULT 'v1.0',
    category_id TEXT,
    subtype_id TEXT,
    confidence NUMERIC,

    -- Deduplication
    content_hash TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_content_hash UNIQUE (content_hash)
);

CREATE INDEX IF NOT EXISTS idx_observation_pointers_source ON public.raw_observation_pointers_v1 (source, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_observation_pointers_category ON public.raw_observation_pointers_v1 (category_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_observation_pointers_taxonomy ON public.raw_observation_pointers_v1 (taxonomy_version);
CREATE INDEX IF NOT EXISTS idx_observation_pointers_hash ON public.raw_observation_pointers_v1 (content_hash);

-- ============================================================================
-- Table: training_candidates_v1
-- Normalized training candidates derived from raw observations
-- Ready for model training with required attributes
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.training_candidates_v1 (
    candidate_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES public.raw_observation_pointers_v1(observation_id),

    -- Taxonomy
    category_id TEXT NOT NULL,
    subtype_id TEXT,
    taxonomy_version TEXT NOT NULL DEFAULT 'v1.0',

    -- Required attributes for training
    required_attrs_json JSONB DEFAULT '{}'::JSONB,

    -- Price quantiles (from similar items or model inference)
    price_q10 NUMERIC,
    price_q50 NUMERIC,
    price_q90 NUMERIC,

    -- Confidence and state
    confidence NUMERIC,
    label_state TEXT NOT NULL DEFAULT 'pending' CHECK (label_state IN ('pending', 'verified', 'rejected')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_candidates_category ON public.training_candidates_v1 (category_id, label_state);
CREATE INDEX IF NOT EXISTS idx_training_candidates_taxonomy ON public.training_candidates_v1 (taxonomy_version);
CREATE INDEX IF NOT EXISTS idx_training_candidates_state ON public.training_candidates_v1 (label_state);

-- ============================================================================
-- Table: user_feedback_events_v1
-- User edits, overrides, and verified sales for calibration
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.user_feedback_events_v1 (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    item_id TEXT,                          -- Reference to user's item
    candidate_id TEXT REFERENCES public.training_candidates_v1(candidate_id),

    -- Feedback type and value
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('sale_price', 'price_correction', 'category_correction', 'verified_sale')),
    value_json JSONB NOT NULL,            -- {price: 123.45, currency: 'EUR', notes: '...'}

    -- Metadata
    source TEXT DEFAULT 'app',            -- 'app', 'admin', 'import'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_feedback_user ON public.user_feedback_events_v1 (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_feedback_candidate ON public.user_feedback_events_v1 (candidate_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON public.user_feedback_events_v1 (feedback_type);

-- ============================================================================
-- View: v_ingest_stats_daily
-- Daily ingest statistics for monitoring
-- ============================================================================
CREATE OR REPLACE VIEW public.v_ingest_stats_daily AS
SELECT
    DATE_TRUNC('day', started_at) AS day,
    COUNT(*) AS run_count,
    SUM(input_count) AS total_input,
    SUM(processed_count) AS total_processed,
    SUM(skipped_count) AS total_skipped,
    SUM(error_count) AS total_errors,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed_runs,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed_runs
FROM public.ingest_runs_v1
GROUP BY DATE_TRUNC('day', started_at)
ORDER BY day DESC;

-- ============================================================================
-- RLS Policies (service role only for ingest tables)
-- ============================================================================
ALTER TABLE public.ingest_runs_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raw_observation_pointers_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_candidates_v1 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_feedback_events_v1 ENABLE ROW LEVEL SECURITY;

-- Service role can do anything
CREATE POLICY "service_role_ingest_runs" ON public.ingest_runs_v1
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_observation_pointers" ON public.raw_observation_pointers_v1
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_training_candidates" ON public.training_candidates_v1
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Users can read training candidates (for transparency)
CREATE POLICY "users_read_training_candidates" ON public.training_candidates_v1
    FOR SELECT TO authenticated USING (true);

-- Users can insert their own feedback
CREATE POLICY "users_insert_feedback" ON public.user_feedback_events_v1
    FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_read_own_feedback" ON public.user_feedback_events_v1
    FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "service_role_feedback" ON public.user_feedback_events_v1
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- Trigger: Update training_candidates_v1.updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_training_candidate_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_training_candidates_updated ON public.training_candidates_v1;
CREATE TRIGGER trg_training_candidates_updated
    BEFORE UPDATE ON public.training_candidates_v1
    FOR EACH ROW EXECUTE FUNCTION update_training_candidate_timestamp();

-- ============================================================================
-- Comment: How to remap taxonomy later
-- ============================================================================
COMMENT ON TABLE public.raw_observation_pointers_v1 IS
'Pointers to raw observation data stored in S3. taxonomy_version tracks which
mapping rules were used. To remap: (1) update taxonomy patterns in code,
(2) increment TAXONOMY_VERSION, (3) run remapping job that reads from S3 and
writes new pointers/candidates with new taxonomy_version, (4) optionally
archive old pointers after verification.';
