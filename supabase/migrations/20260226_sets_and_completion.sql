-- =============================================================
-- Sets & Collection Completion Tracking
-- 2026-02-26
-- =============================================================

-- Sets table (e.g., "Pokemon Base Set", "LEGO UCS Star Destroyer")
CREATE TABLE IF NOT EXISTS public.sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  total_items INT NOT NULL DEFAULT 0,
  release_date DATE,
  image_url TEXT,
  external_id TEXT, -- e.g., set number from TCGPlayer/BrickLink
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Items that belong to sets (catalog_item_id references category_items table)
CREATE TABLE IF NOT EXISTS public.set_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  set_id UUID NOT NULL REFERENCES public.sets(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  position INT, -- number/order within the set
  external_id TEXT, -- card number, piece ID, etc.
  image_url TEXT,
  rarity TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User's progress on sets
CREATE TABLE IF NOT EXISTS public.user_set_progress (
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  set_id UUID NOT NULL REFERENCES public.sets(id) ON DELETE CASCADE,
  owned_item_ids UUID[] DEFAULT '{}',
  owned_count INT NOT NULL DEFAULT 0,
  completion_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, set_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sets_category ON public.sets(category_id);
CREATE INDEX IF NOT EXISTS idx_set_items_set ON public.set_items(set_id);
CREATE INDEX IF NOT EXISTS idx_user_set_progress_user ON public.user_set_progress(user_id);

-- RLS
ALTER TABLE public.sets ENABLE ROW LEVEL SECURITY;
CREATE POLICY sets_read ON public.sets FOR SELECT USING (true);

ALTER TABLE public.set_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY set_items_read ON public.set_items FOR SELECT USING (true);

ALTER TABLE public.user_set_progress ENABLE ROW LEVEL SECURITY;
CREATE POLICY usp_select ON public.user_set_progress FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY usp_insert ON public.user_set_progress FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY usp_update ON public.user_set_progress FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY usp_delete ON public.user_set_progress FOR DELETE USING (auth.uid() = user_id);
