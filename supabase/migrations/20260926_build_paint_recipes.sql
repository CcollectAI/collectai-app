-- Paint recipes on build_paint_projects (2026-09-26).
--
-- 20260226_size_tracking.sql added this column in the repo and was never
-- applied to prod, so saving a recipe failed with PGRST204 "Could not find the
-- 'paint_recipes' column" for every member (walked on Android). Only the
-- recipes half is applied here; that file's item_size/size_system columns
-- have no reader yet and are left for their own decision.
ALTER TABLE public.build_paint_projects
  ADD COLUMN IF NOT EXISTS paint_recipes JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.build_paint_projects.paint_recipes IS
  'Array of paint recipe objects: [{name, paints: [{brand, color, type}], notes}]';

-- PostgREST caches the schema; reload so the new column is writable at once.
NOTIFY pgrst, 'reload schema';
