-- =============================================================================
-- Size-specific pricing + Paint recipes
-- =============================================================================
-- Feature 1: Size tracking for sneakers (US/EU/UK) and watches (mm case diameter)
-- Feature 2: Paint recipes JSONB on build_paint_projects for Warhammer/Gunpla

-- ── 1. Size columns on items — SUPERSEDED, never applied (2026-09-26) ─────────
-- Prod has neither column (information_schema, 2026-09-26), and nothing reads
-- or writes them: the item screen keeps size in items.attrs (`size_system` and
-- the size value — app/item/[id].tsx, categoryFields.ts). Left commented so a
-- manual re-run of this file cannot add two columns nobody uses. Section 2
-- (paint_recipes) was applied by 20260926_build_paint_recipes.sql.
--
-- ALTER TABLE public.items ADD COLUMN IF NOT EXISTS item_size TEXT DEFAULT NULL;
-- ALTER TABLE public.items ADD COLUMN IF NOT EXISTS size_system TEXT DEFAULT NULL
--   CHECK (size_system IN ('us', 'eu', 'uk', 'cm', 'mm'));
-- CREATE INDEX IF NOT EXISTS idx_items_size
--   ON public.items(category, item_size) WHERE item_size IS NOT NULL;

-- ── 2. Paint recipes on build_paint_projects ─────────────────────────────────
ALTER TABLE public.build_paint_projects ADD COLUMN IF NOT EXISTS paint_recipes JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.build_paint_projects.paint_recipes IS
  'Array of paint recipe objects: [{name, paints: [{brand, color, type}], notes}]';
