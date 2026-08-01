-- Fix item_images: the 2026-02-26 migration silently no-opped.
--
-- 20260226_item_images.sql declares the schema the API actually writes
-- (image_url, label, position). It used CREATE TABLE IF NOT EXISTS, and a
-- DIFFERENT public.item_images already existed:
--
--     id, user_id NOT NULL, item_id, url, created_at
--
-- so the migration reported success and did nothing. The columns the code
-- inserts have never existed, and item_images_router.py has been 500ing on
-- every add-photo since:
--
--     POST /items/{id}/images -> 500 {"code":"DB_ERROR",
--                                     "detail":"Failed to add item image"}
--
-- Confirmed on Android 2026-08-01: pick photo -> label -> crop all work, then
-- the upload 500s. `SELECT MAX(position)` in that handler would fail too, and
-- the required user_id is never supplied by the insert.
--
-- Safe to rebuild rather than patch: the stale table holds 0 rows (verified in
-- prod), has no dependent index beyond its pkey, and its single RLS policy is
-- superseded below. Ownership is derived through items, so the stale
-- user_id column is not needed.
--
-- After applying, regenerate schema.lock.json — ANY DDL stales it and the next
-- bake restart hard-downs the API (scripts/regen_schema_lock.py).

BEGIN;

DROP TABLE IF EXISTS public.item_images CASCADE;

CREATE TABLE public.item_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id UUID NOT NULL REFERENCES public.items(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  label TEXT CHECK (label IN ('front', 'back', 'detail', 'box', 'certificate', 'damage', 'other')),
  position INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_item_images_item ON public.item_images(item_id, position);

ALTER TABLE public.item_images ENABLE ROW LEVEL SECURITY;

CREATE POLICY item_images_select ON public.item_images FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

CREATE POLICY item_images_insert ON public.item_images FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

CREATE POLICY item_images_update ON public.item_images FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

CREATE POLICY item_images_delete ON public.item_images FOR DELETE USING (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

COMMIT;

-- The label CHECK is the exact allow-list the client sends. The Android photo
-- picker offers "No label / Front / Back"; the API must lowercase before
-- insert or the CHECK rejects 'FRONT'. See item_images_router.py.
