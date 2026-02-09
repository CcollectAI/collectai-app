-- Migration: Add canary deployment support + materialized views
-- Date: 2026-02-09
-- Tasks: #13 (canary), #15 (feedback consolidation), #21 (materialized views)

-- ===================================================================
-- #13: Add is_canary flag to model_registry for canary deployments
-- ===================================================================

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'model_registry' AND column_name = 'is_canary'
  ) THEN
    ALTER TABLE public.model_registry
      ADD COLUMN is_canary boolean DEFAULT false;
  END IF;
END $$;

-- Index for canary model lookup
CREATE INDEX IF NOT EXISTS idx_model_registry_canary
  ON public.model_registry (category, is_canary, created_at DESC)
  WHERE is_canary = true;

-- Index for active production model lookup
CREATE INDEX IF NOT EXISTS idx_model_registry_active_prod
  ON public.model_registry (category, is_active, created_at DESC)
  WHERE is_active = true AND (is_canary IS NULL OR is_canary = false);


-- ===================================================================
-- #15: Deprecate legacy feedback table, add redirect view
-- ===================================================================

-- Add a comment marking the legacy table as deprecated
COMMENT ON TABLE public.feedback IS
  'DEPRECATED: Use user_feedback_events_v1 instead. This table is kept for backward compatibility.';

-- Create a unified view that merges both tables
CREATE OR REPLACE VIEW public.v_all_feedback_v1 AS
  -- From new table
  SELECT
    id,
    user_id,
    item_id,
    feedback_type,
    value_json,
    created_at,
    'user_feedback_events_v1' AS source_table
  FROM public.user_feedback_events_v1
  UNION ALL
  -- From legacy table
  SELECT
    id,
    NULL AS user_id,
    item_id,
    label AS feedback_type,
    NULL AS value_json,
    observed_at AS created_at,
    'feedback' AS source_table
  FROM public.feedback;


-- ===================================================================
-- #21: Materialized view for category summaries (performance at scale)
-- ===================================================================

-- Drop if exists to recreate
DROP MATERIALIZED VIEW IF EXISTS public.mv_category_summaries_v1;

CREATE MATERIALIZED VIEW public.mv_category_summaries_v1 AS
SELECT
  ci.category,
  COUNT(ci.id) AS total_count,
  COUNT(uco.id) AS owned_count,
  COUNT(ci.id) - COUNT(uco.id) AS missing_count,
  CASE
    WHEN COUNT(ci.id) > 0
    THEN ROUND(100.0 * COUNT(uco.id) / COUNT(ci.id), 1)
    ELSE 0
  END AS completion_pct,
  uco.user_id
FROM public.category_items ci
LEFT JOIN public.user_category_ownership uco
  ON uco.category_item_id = ci.id
GROUP BY ci.category, uco.user_id;

-- Index for fast per-user lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_category_summaries_user_cat
  ON public.mv_category_summaries_v1 (user_id, category);

-- Refresh function (call from cron or after imports)
CREATE OR REPLACE FUNCTION public.refresh_category_summaries()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_category_summaries_v1;
END;
$$;


-- ===================================================================
-- Prometheus-compatible coverage gauge for calibration drift alerting
-- ===================================================================

-- Table for storing calibration snapshots (used by calibration_job.py)
CREATE TABLE IF NOT EXISTS public.calibration_snapshots (
  id bigserial PRIMARY KEY,
  category text NOT NULL,
  picp float NOT NULL,
  ace float NOT NULL,
  mae float NOT NULL,
  samples int NOT NULL,
  gate_pass boolean NOT NULL DEFAULT true,
  gate_reasons text[] DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_calibration_snapshots_cat_time
  ON public.calibration_snapshots (category, created_at DESC);
