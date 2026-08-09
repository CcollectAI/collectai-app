-- Restore v_images_needing_embeddings, dropped by the CASCADE in
-- 20260801_fix_item_images_schema.sql (it depended on item_images).
--
-- Consumer: ops/embed_images.py, which selects image_id, path_like, created_at
-- and upserts into item_image_embeddings keyed by image_id. Rebuilt against the
-- corrected column name (image_url, formerly url).
--
-- Both tables were empty at the time of the rebuild, so no rows were lost.

CREATE OR REPLACE VIEW public.v_images_needing_embeddings AS
SELECT
  i.id            AS image_id,
  i.image_url     AS path_like,
  i.created_at    AS created_at
FROM public.item_images i
LEFT JOIN public.item_image_embeddings e ON e.image_id = i.id
WHERE e.image_id IS NULL
  AND i.image_url IS NOT NULL
  AND trim(i.image_url) <> '';
