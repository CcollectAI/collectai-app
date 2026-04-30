-- Fix rpc_create_build_paint_project_v1 column drift. The RPC body
-- referenced title / percent_complete / is_completed / updated_at —
-- none of which exist on the live build_paint_projects table.
-- Real columns: name, progress_pct, status, last_updated.

CREATE OR REPLACE FUNCTION public.rpc_create_build_paint_project_v1(
  p_title       text,
  p_category    text DEFAULT NULL::text,
  p_category_id text DEFAULT NULL::text,
  p_item_id     uuid DEFAULT NULL::uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_uid uuid := auth.uid();
  v_project_id text;
  v_resolved_category_id text;
  v_result jsonb;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  v_resolved_category_id := p_category_id;
  IF p_item_id IS NOT NULL AND v_resolved_category_id IS NULL THEN
    SELECT category INTO v_resolved_category_id
    FROM public.items
    WHERE id = p_item_id AND user_id = v_uid;
  END IF;

  -- Real columns: name (not title), progress_pct (not percent_complete),
  -- last_updated (not updated_at). is_completed is derived from status.
  INSERT INTO public.build_paint_projects (
    id, user_id, name, category, category_id, item_id,
    progress_pct, status, created_at, last_updated
  ) VALUES (
    gen_random_uuid()::text, v_uid, p_title, p_category, v_resolved_category_id, p_item_id,
    0, 'Backlog', now(), now()
  )
  RETURNING id INTO v_project_id;

  SELECT jsonb_build_object(
    'id', bp.id,
    'title', bp.name,
    'category', bp.category,
    'category_id', bp.category_id,
    'item_id', bp.item_id,
    'status', bp.status,
    'percent_complete', bp.progress_pct,
    'is_completed', (lower(coalesce(bp.status,'')) IN ('finished','completed','displayed')),
    'notes', bp.notes,
    'created_at', bp.created_at,
    'updated_at', bp.last_updated
  ) INTO v_result
  FROM public.build_paint_projects bp
  WHERE bp.id = v_project_id;

  RETURN v_result;
END;
$function$;
