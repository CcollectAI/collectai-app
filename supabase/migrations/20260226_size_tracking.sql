-- =============================================================================
-- Size-specific pricing + Paint recipes
-- =============================================================================
-- Feature 1: Size tracking for sneakers (US/EU/UK) and watches (mm case diameter)
-- Feature 2: Paint recipes JSONB on build_paint_projects for Warhammer/Gunpla

-- ── 1. Size columns on items ─────────────────────────────────────────────────
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS item_size TEXT DEFAULT NULL;
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS size_system TEXT DEFAULT NULL
  CHECK (size_system IN ('us', 'eu', 'uk', 'cm', 'mm'));

CREATE INDEX IF NOT EXISTS idx_items_size
  ON public.items(category, item_size) WHERE item_size IS NOT NULL;

COMMENT ON COLUMN public.items.item_size IS
  'Size value — e.g. "10.5" for sneakers (US), "42mm" for watches';
COMMENT ON COLUMN public.items.size_system IS
  'Size measurement system: us/eu/uk for sneakers, mm for watches';

-- ── 2. Paint recipes on build_paint_projects ─────────────────────────────────
ALTER TABLE public.build_paint_projects ADD COLUMN IF NOT EXISTS paint_recipes JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.build_paint_projects.paint_recipes IS
  'Array of paint recipe objects: [{name, paints: [{brand, color, type}], notes}]';
