-- ============================================================================
-- Migration: Category-specific project status pipelines
-- Date: 2026-03-22
--
-- Replaces the coarse Active/Backlog/Completed status system with granular,
-- category-specific status pipelines (e.g. Warhammer: wishlist → purchased →
-- unassembled → assembled → primed → battle_ready → parade_ready → finished).
--
-- Changes:
--   1. Migrate existing statuses to new values (Active→in_progress, Backlog→wishlist, Completed→finished)
--   2. Update default status from 'Active' to 'wishlist'
--   3. Update RPC functions to use new status values
--   4. Add CHECK constraint for valid statuses
-- ============================================================================

-- Step 1: Migrate existing status values to new pipeline values
UPDATE public.build_paint_projects
SET status = CASE
  WHEN lower(status) = 'active'    THEN 'in_progress'
  WHEN lower(status) = 'backlog'   THEN 'wishlist'
  WHEN lower(status) = 'completed' THEN 'finished'
  ELSE lower(status)  -- already lowercase or new-format
END
WHERE status IS NOT NULL;

-- Step 2: Change default from 'Active' to 'wishlist'
ALTER TABLE public.build_paint_projects
  ALTER COLUMN status SET DEFAULT 'wishlist';

-- Step 3: Add CHECK constraint for all valid statuses across all category pipelines
-- We allow all statuses from all category pipelines plus legacy values for safety
DO $$
BEGIN
  -- Drop existing constraint if any
  ALTER TABLE public.build_paint_projects DROP CONSTRAINT IF EXISTS build_paint_projects_status_check;

  -- Add new constraint covering all valid statuses across all category pipelines
  ALTER TABLE public.build_paint_projects ADD CONSTRAINT build_paint_projects_status_check
    CHECK (status IN (
      -- Universal statuses (all categories)
      'wishlist', 'purchased', 'in_progress', 'finished',
      -- Assembly statuses (warhammer, scale_models, gunpla, keycaps, diecast)
      'unassembled', 'assembled',
      -- Paint/surface statuses (warhammer, scale_models, gunpla, designer_toys, diecast)
      'primed', 'painted',
      -- Warhammer-specific (GW painting standard terminology)
      'battle_ready', 'parade_ready',
      -- Scale models / gunpla
      'weathered', 'decaled', 'top_coated',
      -- LEGO
      'sealed', 'built', 'modified', 'displayed',
      -- Keycaps
      'parts_received', 'lubing', 'tuned',
      -- Designer toys
      'unboxed', 'customizing',
      -- Diecast
      'stock', 'disassembled', 'detailed'
    ));
END $$;

-- Step 4: Update the create project RPC to default to 'wishlist'
CREATE OR REPLACE FUNCTION rpc_create_build_paint_project_v1(
  p_title text,
  p_category text DEFAULT NULL,
  p_category_id text DEFAULT NULL,
  p_item_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_uid uuid := auth.uid();
  v_project_id uuid;
  v_result jsonb;
  v_resolved_category_id text;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Resolve category_id from item if not provided
  IF p_category_id IS NOT NULL THEN
    v_resolved_category_id := p_category_id;
  ELSIF p_item_id IS NOT NULL THEN
    SELECT category INTO v_resolved_category_id
    FROM public.items
    WHERE id = p_item_id AND user_id = v_uid;
  END IF;

  INSERT INTO build_paint_projects (
    id, user_id, title, category, category_id, item_id,
    percent_complete, is_completed, status, created_at, updated_at
  ) VALUES (
    gen_random_uuid(), v_uid, p_title, p_category, v_resolved_category_id, p_item_id,
    0, false, 'wishlist', now(), now()
  )
  RETURNING id INTO v_project_id;

  SELECT jsonb_build_object(
    'id', bp.id,
    'title', bp.title,
    'category', bp.category,
    'category_id', bp.category_id,
    'item_id', bp.item_id,
    'status', bp.status,
    'percent_complete', bp.percent_complete,
    'is_completed', bp.is_completed,
    'notes', bp.notes,
    'created_at', bp.created_at,
    'updated_at', bp.updated_at
  ) INTO v_result
  FROM build_paint_projects bp
  WHERE bp.id = v_project_id;

  RETURN v_result;
END;
$$;

-- Step 5: Update the mark-complete RPC to use 'finished' instead of 'Completed'/'Active'
CREATE OR REPLACE FUNCTION rpc_mark_build_paint_project_complete_v1(
  p_project_id uuid,
  p_is_completed boolean
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  UPDATE public.build_paint_projects
  SET
    is_completed = p_is_completed,
    percent_complete = CASE WHEN p_is_completed THEN 100 ELSE percent_complete END,
    status = CASE WHEN p_is_completed THEN 'finished' ELSE status END,
    completed_at = CASE WHEN p_is_completed THEN now() ELSE NULL END,
    updated_at = now()
  WHERE id = p_project_id AND user_id = v_user_id;
END;
$$;

-- Step 6: Update the set-progress RPC (no status change needed, just ensure it works)
CREATE OR REPLACE FUNCTION rpc_set_build_paint_progress_v1(
  p_project_id uuid,
  p_percent    integer,
  p_status     text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  UPDATE public.build_paint_projects
  SET
    percent_complete = LEAST(GREATEST(p_percent, 0), 100),
    status = coalesce(p_status, status),
    is_completed = CASE WHEN p_percent >= 100 THEN true ELSE is_completed END,
    completed_at = CASE
      WHEN p_percent >= 100 AND completed_at IS NULL THEN now()
      ELSE completed_at
    END,
    updated_at = now()
  WHERE id = p_project_id AND user_id = v_user_id;
END;
$$;
