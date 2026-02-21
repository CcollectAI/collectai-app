-- ============================================================================
-- Build & Paint Improvements — Category-aware projects + step templates
-- ============================================================================

-- 1a. Add columns to build_paint_projects
ALTER TABLE build_paint_projects
  ADD COLUMN IF NOT EXISTS category_id text,
  ADD COLUMN IF NOT EXISTS item_id uuid REFERENCES items(id) ON DELETE SET NULL;

-- image_url already exists in the schema but ensure it's there
DO $$ BEGIN
  ALTER TABLE build_paint_projects ADD COLUMN IF NOT EXISTS image_url text;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_build_paint_projects_category
  ON build_paint_projects(user_id, category_id)
  WHERE category_id IS NOT NULL;

-- Index for item linking
CREATE INDEX IF NOT EXISTS idx_build_paint_projects_item
  ON build_paint_projects(item_id)
  WHERE item_id IS NOT NULL;

-- 1b. Build step templates table (read-only reference data)
CREATE TABLE IF NOT EXISTS build_step_templates (
  id text PRIMARY KEY,
  display_name text NOT NULL,
  steps jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- No RLS — public read-only reference data
ALTER TABLE build_step_templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY build_step_templates_select ON build_step_templates
  FOR SELECT USING (true);

-- 1c. Seed step templates
INSERT INTO build_step_templates (id, display_name, steps) VALUES
(
  'warhammer',
  'Warhammer Miniatures',
  '[
    {"id":"wh-1","label":"Unbox & inspect sprues","order":1},
    {"id":"wh-2","label":"Clean mold lines & flash","order":2},
    {"id":"wh-3","label":"Dry-fit & plan assembly","order":3},
    {"id":"wh-4","label":"Assemble / sub-assemblies","order":4},
    {"id":"wh-5","label":"Prime (zenithal or flat)","order":5},
    {"id":"wh-6","label":"Base colors","order":6},
    {"id":"wh-7","label":"Washes & shading","order":7},
    {"id":"wh-8","label":"Layer highlights","order":8},
    {"id":"wh-9","label":"Details (eyes, gems, metallics)","order":9},
    {"id":"wh-10","label":"Basing","order":10},
    {"id":"wh-11","label":"Varnish & seal","order":11},
    {"id":"wh-12","label":"Photography & display","order":12}
  ]'::jsonb
),
(
  'gunpla',
  'Gunpla / Model Kits',
  '[
    {"id":"gp-1","label":"Unbox & organize runners","order":1},
    {"id":"gp-2","label":"Nub removal & cleanup","order":2},
    {"id":"gp-3","label":"Test fit / dry assembly","order":3},
    {"id":"gp-4","label":"Panel line scribing (optional)","order":4},
    {"id":"gp-5","label":"Surface prep & sanding","order":5},
    {"id":"gp-6","label":"Primer coat","order":6},
    {"id":"gp-7","label":"Base paint / color separation","order":7},
    {"id":"gp-8","label":"Detail painting","order":8},
    {"id":"gp-9","label":"Decals / waterslide","order":9},
    {"id":"gp-10","label":"Panel lining","order":10},
    {"id":"gp-11","label":"Top coat / clear coat","order":11},
    {"id":"gp-12","label":"Final assembly & posing","order":12}
  ]'::jsonb
),
(
  'lego',
  'LEGO',
  '[
    {"id":"lg-1","label":"Sort pieces by bag/color","order":1},
    {"id":"lg-2","label":"Build phase 1 (base/frame)","order":2},
    {"id":"lg-3","label":"Build phase 2 (details)","order":3},
    {"id":"lg-4","label":"Build phase 3 (finishing)","order":4},
    {"id":"lg-5","label":"Sticker/decal application","order":5},
    {"id":"lg-6","label":"Minifigure assembly","order":6},
    {"id":"lg-7","label":"Final inspection","order":7},
    {"id":"lg-8","label":"Display setup","order":8}
  ]'::jsonb
),
(
  'scale_models',
  'Scale Models',
  '[
    {"id":"sm-1","label":"Research & reference gathering","order":1},
    {"id":"sm-2","label":"Dry fit & test assembly","order":2},
    {"id":"sm-3","label":"Cockpit / interior detail","order":3},
    {"id":"sm-4","label":"Main assembly","order":4},
    {"id":"sm-5","label":"Filling & sanding seams","order":5},
    {"id":"sm-6","label":"Primer coat","order":6},
    {"id":"sm-7","label":"Pre-shading","order":7},
    {"id":"sm-8","label":"Base camouflage / color","order":8},
    {"id":"sm-9","label":"Decals & markings","order":9},
    {"id":"sm-10","label":"Weathering (washes, chipping, streaking)","order":10},
    {"id":"sm-11","label":"Clear coat","order":11},
    {"id":"sm-12","label":"Final details (antenna, lights, rigging)","order":12}
  ]'::jsonb
),
(
  'generic',
  'Generic / Other',
  '[
    {"id":"gen-1","label":"Preparation & planning","order":1},
    {"id":"gen-2","label":"Assembly","order":2},
    {"id":"gen-3","label":"Surface prep","order":3},
    {"id":"gen-4","label":"Priming","order":4},
    {"id":"gen-5","label":"Base coating","order":5},
    {"id":"gen-6","label":"Detailing","order":6},
    {"id":"gen-7","label":"Finishing & sealing","order":7}
  ]'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  steps = EXCLUDED.steps;

-- 1c. Update RPC to accept category_id and item_id
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
  v_resolved_category_id text;
  v_result jsonb;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- If item_id provided, resolve category_id from the item
  v_resolved_category_id := p_category_id;
  IF p_item_id IS NOT NULL AND v_resolved_category_id IS NULL THEN
    SELECT category INTO v_resolved_category_id
    FROM items
    WHERE id = p_item_id AND user_id = v_uid;
  END IF;

  INSERT INTO build_paint_projects (
    id, user_id, title, category, category_id, item_id,
    percent_complete, is_completed, status, created_at, updated_at
  ) VALUES (
    gen_random_uuid(), v_uid, p_title, p_category, v_resolved_category_id, p_item_id,
    0, false, 'Backlog', now(), now()
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

-- 1d. Update view to include new columns + linked item info
CREATE OR REPLACE VIEW v_build_paint_projects_v1 AS
SELECT
  bp.id,
  bp.title,
  bp.category,
  bp.category_id,
  bp.item_id,
  bp.status,
  bp.percent_complete,
  bp.is_completed,
  bp.notes,
  bp.image_url,
  bp.created_at,
  bp.updated_at,
  i.title AS item_name,
  i.images AS item_images
FROM build_paint_projects bp
LEFT JOIN items i ON bp.item_id = i.id
WHERE bp.user_id = auth.uid();
