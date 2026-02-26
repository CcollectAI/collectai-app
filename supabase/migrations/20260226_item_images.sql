-- Multi-photo per item: item_images table with labels and ordering
-- Each item can have multiple images with labels (front, back, detail, box, etc.)

CREATE TABLE IF NOT EXISTS public.item_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id UUID NOT NULL REFERENCES public.items(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  label TEXT CHECK (label IN ('front', 'back', 'detail', 'box', 'certificate', 'damage', 'other')),
  position INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast lookup by item, ordered by position
CREATE INDEX idx_item_images_item ON public.item_images(item_id, position);

-- Enable RLS
ALTER TABLE public.item_images ENABLE ROW LEVEL SECURITY;

-- Users can only see images for their own items
CREATE POLICY item_images_select ON public.item_images FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

-- Users can only add images to their own items
CREATE POLICY item_images_insert ON public.item_images FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

-- Users can only update images on their own items (for reordering)
CREATE POLICY item_images_update ON public.item_images FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);

-- Users can only delete images from their own items
CREATE POLICY item_images_delete ON public.item_images FOR DELETE USING (
  EXISTS (SELECT 1 FROM public.items WHERE id = item_images.item_id AND user_id = auth.uid())
);
