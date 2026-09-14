-- 2026-09-14 — real set names on the "Browse by Set" rail.
--
-- The rail printed set CODES: Pokémon's top sets read "Swsh8" and "Smp" (Fusion
-- Strike, SM Black Star Promos) because the endpoint's only label source was
-- `_humanize_set_code(set_code)`. The real name was already in the catalogue:
-- `category_items.attributes_json->>'set'`.
--
-- Measured on prod before writing this (read-only):
--   * pokemon, mtg, lorcana, yugioh, sportscards: every top-12 set has exactly
--     ONE distinct name; no category has a set with two.
--   * sportscards reuses a name across years — 2023-panini-prizm and
--     2024-panini-prizm are both "Panini Prizm". A name is therefore used only
--     when it is UNIQUE within its category; otherwise `set_name` is NULL and the
--     endpoint falls back to the code ("2023 Panini Prizm"), which keeps the year.
--   * result: 1,048 of 14,982 groups named; row count unchanged; body builds in
--     0.7s (refresh is nightly, pg_cron jobid 42, CONCURRENTLY — needs the unique
--     index below).
--
-- Additive for the schema lock (same MV name, one extra column), but DROP +
-- CREATE is still DDL: regenerate the lock and run preflight_schema_lock before
-- any restart (CLAUDE.md, "DDL stales the lock").
--
-- Grants: DROP discards the MV's ACL. Run this as `postgres` (DB_DSN_DIRECT):
-- the public-schema default privileges for objects `postgres` creates reproduce
-- the current ACL exactly (anon/authenticated/service_role arwdDxtm,
-- collector_bot arwd — checked 2026-09-14). Verify after applying:
--   SELECT relacl FROM pg_class WHERE relname = 'mv_catalog_collections';
--
-- One transaction, so readers see the old MV until the new one commits.

BEGIN;

DROP MATERIALIZED VIEW IF EXISTS public.mv_catalog_collections;
CREATE MATERIALIZED VIEW public.mv_catalog_collections AS
  WITH sets AS (
    SELECT category, set_code AS grp,
           COUNT(*) AS total_items,
           (ARRAY_AGG(image_url) FILTER (WHERE image_url IS NOT NULL AND image_url <> ''))[1] AS cover_image,
           CASE WHEN COUNT(DISTINCT NULLIF(attributes_json->>'set', '')) = 1
                THEN MIN(NULLIF(attributes_json->>'set', '')) END AS name_candidate
    FROM public.category_items
    WHERE set_code IS NOT NULL AND set_code <> ''
    GROUP BY category, set_code
  )
  SELECT category, 'set'::text AS dim, grp, total_items, cover_image,
         CASE WHEN name_candidate IS NOT NULL
               AND COUNT(*) OVER (PARTITION BY category, name_candidate) = 1
              THEN name_candidate END AS set_name
  FROM sets
  UNION ALL
  SELECT category, 'brand'::text AS dim, brand AS grp,
         COUNT(*) AS total_items,
         (ARRAY_AGG(image_url) FILTER (WHERE image_url IS NOT NULL AND image_url <> ''))[1] AS cover_image,
         NULL::text AS set_name
  FROM public.category_items
  WHERE brand IS NOT NULL AND brand <> ''
  GROUP BY category, brand;

CREATE UNIQUE INDEX uq_mv_catalog_collections ON public.mv_catalog_collections (category, dim, grp);
CREATE INDEX idx_mv_catalog_collections_read ON public.mv_catalog_collections (category, dim, total_items DESC);

COMMIT;

ANALYZE public.mv_catalog_collections;
