-- Migration: Category Completion (Moat Gap Phase 3)
-- Creates taxonomy tables and views for tracking collection completeness

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Category Items Taxonomy Table
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.category_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category text NOT NULL,
  set_code text,
  item_key text NOT NULL,
  title text NOT NULL,
  brand text,
  rarity text,
  notes text,
  image_url text,
  external_id text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(category, item_key)
);

-- Index for category lookups
CREATE INDEX IF NOT EXISTS idx_category_items_category ON public.category_items(category);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. User Category Ownership Table
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.user_category_ownership (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  category_item_id uuid NOT NULL REFERENCES public.category_items(id) ON DELETE CASCADE,
  quantity int DEFAULT 1,
  notes text,
  acquired_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),
  UNIQUE(user_id, category_item_id)
);

-- Index for user lookups
CREATE INDEX IF NOT EXISTS idx_user_category_ownership_user_id ON public.user_category_ownership(user_id);
CREATE INDEX IF NOT EXISTS idx_user_category_ownership_category_item ON public.user_category_ownership(category_item_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Row Level Security (RLS)
-- ─────────────────────────────────────────────────────────────────────────────

-- category_items: Public read (taxonomy is shared)
ALTER TABLE public.category_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "category_items_select_all"
  ON public.category_items FOR SELECT
  USING (true);

-- user_category_ownership: Owner-only
ALTER TABLE public.user_category_ownership ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_category_ownership_select_own"
  ON public.user_category_ownership FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "user_category_ownership_insert_own"
  ON public.user_category_ownership FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "user_category_ownership_update_own"
  ON public.user_category_ownership FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "user_category_ownership_delete_own"
  ON public.user_category_ownership FOR DELETE
  USING (auth.uid() = user_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Category Summaries View
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW public.v_category_summaries_v1 AS
SELECT
  ci.category AS id,
  ci.category AS name,
  COUNT(DISTINCT ci.id) AS total_count,
  COUNT(DISTINCT uco.category_item_id) AS owned_count,
  COUNT(DISTINCT ci.id) - COUNT(DISTINCT uco.category_item_id) AS missing_count,
  CASE
    WHEN COUNT(DISTINCT ci.id) = 0 THEN 0
    ELSE ROUND((COUNT(DISTINCT uco.category_item_id)::numeric / COUNT(DISTINCT ci.id)::numeric) * 100, 1)
  END AS completion_pct
FROM public.category_items ci
LEFT JOIN public.user_category_ownership uco
  ON uco.category_item_id = ci.id
  AND uco.user_id = auth.uid()
GROUP BY ci.category
ORDER BY ci.category;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Category Missing Items View
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW public.v_category_missing_items_v1 AS
SELECT
  ci.id,
  ci.category AS category_id,
  ci.title,
  ci.brand,
  ci.rarity,
  ci.notes,
  ci.image_url
FROM public.category_items ci
WHERE NOT EXISTS (
  SELECT 1
  FROM public.user_category_ownership uco
  WHERE uco.category_item_id = ci.id
    AND uco.user_id = auth.uid()
)
ORDER BY ci.category, ci.title;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Mark Category Item Owned RPC
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_mark_category_item_owned_v1(
  p_category_item_id uuid,
  p_quantity int DEFAULT 1,
  p_notes text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_result jsonb;
BEGIN
  -- Validate user is authenticated
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Validate category item exists
  IF NOT EXISTS (SELECT 1 FROM public.category_items WHERE id = p_category_item_id) THEN
    RAISE EXCEPTION 'Category item not found';
  END IF;

  -- Upsert ownership record
  INSERT INTO public.user_category_ownership (user_id, category_item_id, quantity, notes)
  VALUES (v_user_id, p_category_item_id, COALESCE(p_quantity, 1), p_notes)
  ON CONFLICT (user_id, category_item_id)
  DO UPDATE SET
    quantity = EXCLUDED.quantity,
    notes = COALESCE(EXCLUDED.notes, user_category_ownership.notes),
    created_at = now();

  -- Return success
  v_result := jsonb_build_object(
    'success', true,
    'category_item_id', p_category_item_id,
    'quantity', p_quantity
  );

  RETURN v_result;
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Unmark Category Item Owned RPC (for toggling)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.rpc_unmark_category_item_owned_v1(
  p_category_item_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  -- Validate user is authenticated
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Delete ownership record
  DELETE FROM public.user_category_ownership
  WHERE user_id = v_user_id
    AND category_item_id = p_category_item_id;

  RETURN jsonb_build_object('success', true);
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. Feedback Table (for Phase 2, if not exists)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid,
  user_id uuid DEFAULT auth.uid(),
  label text NOT NULL,
  notes text,
  observed_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

-- RLS for feedback
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "feedback_insert_authenticated"
  ON public.feedback FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "feedback_select_own"
  ON public.feedback FOR SELECT
  USING (auth.uid() = user_id);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_feedback_item_id ON public.feedback(item_id);
CREATE INDEX IF NOT EXISTS idx_feedback_observed_at ON public.feedback(observed_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- 9. Training Items Correction Columns (if not exists)
-- ─────────────────────────────────────────────────────────────────────────────

-- Add correction columns to training_items if table exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'training_items' AND table_schema = 'public') THEN
    -- Add corrected_price column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'training_items' AND column_name = 'corrected_price') THEN
      ALTER TABLE public.training_items ADD COLUMN corrected_price numeric;
    END IF;

    -- Add corrected_condition column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'training_items' AND column_name = 'corrected_condition') THEN
      ALTER TABLE public.training_items ADD COLUMN corrected_condition text;
    END IF;

    -- Add corrected_category column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'training_items' AND column_name = 'corrected_category') THEN
      ALTER TABLE public.training_items ADD COLUMN corrected_category text;
    END IF;

    -- Add corrected_attributes column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'training_items' AND column_name = 'corrected_attributes') THEN
      ALTER TABLE public.training_items ADD COLUMN corrected_attributes jsonb;
    END IF;

    -- Add correction_notes column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'training_items' AND column_name = 'correction_notes') THEN
      ALTER TABLE public.training_items ADD COLUMN correction_notes text;
    END IF;

    -- Add corrected_at column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'training_items' AND column_name = 'corrected_at') THEN
      ALTER TABLE public.training_items ADD COLUMN corrected_at timestamptz;
    END IF;
  END IF;
END $$;
