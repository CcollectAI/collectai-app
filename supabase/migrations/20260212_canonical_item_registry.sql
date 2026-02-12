-- Canonical Item Registry Migration
-- Adds canonical_item_id FK to items, creates collections + collection_items
-- tables, and creates category_item_variants for variant tracking.
--
-- This enables:
-- - Linking user items to golden records (canonical catalog)
-- - Set/collection completion tracking
-- - Variant multipliers for pricing (1st Edition, Chase, PSA 10, etc.)

BEGIN;

-- =========================================================================
-- 1. Link user items to canonical catalog
-- =========================================================================

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS canonical_item_id uuid
    REFERENCES public.category_items(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_items_canonical_item_id
  ON public.items(canonical_item_id)
  WHERE canonical_item_id IS NOT NULL;

-- =========================================================================
-- 2. Enhance category_items (canonical catalog) with more fields
-- =========================================================================

ALTER TABLE public.category_items
  ADD COLUMN IF NOT EXISTS barcode text,
  ADD COLUMN IF NOT EXISTS attributes_json jsonb DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS source text DEFAULT 'seed',
  ADD COLUMN IF NOT EXISTS verified boolean DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_category_items_barcode
  ON public.category_items(barcode)
  WHERE barcode IS NOT NULL;

-- =========================================================================
-- 3. Collections (sets) registry
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.collections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category text NOT NULL,
  collection_key text NOT NULL,
  display_name text NOT NULL,
  release_date date,
  total_items int,
  image_url text,
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(category, collection_key)
);

CREATE INDEX IF NOT EXISTS idx_collections_category
  ON public.collections(category);

-- Enable RLS
ALTER TABLE public.collections ENABLE ROW LEVEL SECURITY;

-- Collections are public reference data (read-only for authenticated users)
DROP POLICY IF EXISTS collections_public_select ON public.collections;
CREATE POLICY collections_public_select ON public.collections
  FOR SELECT USING (true);

-- Service role can manage collections
DROP POLICY IF EXISTS collections_service_all ON public.collections;
CREATE POLICY collections_service_all ON public.collections
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

-- =========================================================================
-- 4. Collection items (which canonical items belong to which collection)
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.collection_items (
  collection_id uuid NOT NULL REFERENCES public.collections(id) ON DELETE CASCADE,
  category_item_id uuid NOT NULL REFERENCES public.category_items(id) ON DELETE CASCADE,
  sequence_number int,
  PRIMARY KEY(collection_id, category_item_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_items_category_item
  ON public.collection_items(category_item_id);

-- Enable RLS (public reference data)
ALTER TABLE public.collection_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS collection_items_public_select ON public.collection_items;
CREATE POLICY collection_items_public_select ON public.collection_items
  FOR SELECT USING (true);

DROP POLICY IF EXISTS collection_items_service_all ON public.collection_items;
CREATE POLICY collection_items_service_all ON public.collection_items
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

-- =========================================================================
-- 5. Category item variants (1st Edition, Chase, PSA 10, etc.)
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.category_item_variants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category_item_id uuid NOT NULL REFERENCES public.category_items(id) ON DELETE CASCADE,
  variant_key text NOT NULL,
  display_name text NOT NULL,
  variant_type text,
  multiplier numeric(5,2) DEFAULT 1.0,
  notes text,
  created_at timestamptz DEFAULT now(),
  UNIQUE(category_item_id, variant_key)
);

CREATE INDEX IF NOT EXISTS idx_category_item_variants_item
  ON public.category_item_variants(category_item_id);

-- Enable RLS (public reference data)
ALTER TABLE public.category_item_variants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS variants_public_select ON public.category_item_variants;
CREATE POLICY variants_public_select ON public.category_item_variants
  FOR SELECT USING (true);

DROP POLICY IF EXISTS variants_service_all ON public.category_item_variants;
CREATE POLICY variants_service_all ON public.category_item_variants
  FOR ALL
  USING (current_setting('role', true) = 'service_role')
  WITH CHECK (current_setting('role', true) = 'service_role');

-- =========================================================================
-- 6. User collection completion tracking view
-- =========================================================================

-- Materialized view: for each user, how complete is each collection?
-- (Refreshed by nightly pipeline or on-demand)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_user_collection_progress AS
SELECT
  i.user_id,
  c.id AS collection_id,
  c.category,
  c.collection_key,
  c.display_name,
  c.total_items,
  COUNT(DISTINCT ci.category_item_id) AS owned_items,
  CASE
    WHEN c.total_items IS NOT NULL AND c.total_items > 0
    THEN ROUND(COUNT(DISTINCT ci.category_item_id)::numeric / c.total_items, 3)
    ELSE 0
  END AS completion_ratio
FROM public.items i
JOIN public.collection_items ci ON ci.category_item_id = i.canonical_item_id
JOIN public.collections c ON c.id = ci.collection_id
WHERE i.canonical_item_id IS NOT NULL
GROUP BY i.user_id, c.id, c.category, c.collection_key, c.display_name, c.total_items
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_user_collection_progress_pk
  ON public.mv_user_collection_progress(user_id, collection_id);

COMMIT;
