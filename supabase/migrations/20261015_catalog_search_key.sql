-- Catalogue search that forgives punctuation, spacing, accents and category
-- words (2026-10-15).
--
-- Walked GET /search/unified as a member: "1989 taylors version" found NOTHING
-- (the catalogue says "1989 (Taylor's Version)"), "gameboy" found one oddity
-- (the catalogue says "Game Boy"), and "one piece op01" found 1 card of the
-- 150+ titled "<name> [OP01] (Normal)", because "one piece" is the CATEGORY,
-- not part of any card title. Each typed word was a substring of the TITLE.
--
-- search_key(): lower-case, accents folded (Pokémon -> pokemon), everything
-- that is not a letter or digit removed. Applied to title + ' ' + category on
-- the row side and to each typed word on the query side (in SQL, by the same
-- function, so the two can never normalise differently).
--
-- INDEX JUSTIFICATION (DATA_SCALING_PLAN §6.1): idx_category_items_title_trgm
-- indexes `title` as stored; it cannot serve a LIKE on search_key(title ||
-- category), so without this index every search is a sequential scan over
-- ~240k rows. Write path: category_items is written by catalogue imports in
-- batches; one extra GIN entry per row.
--
-- unaccent() is STABLE because its dictionary is looked up by name; naming the
-- dictionary explicitly (two-argument form, schema-qualified) is the standard
-- way to make an IMMUTABLE wrapper usable in an index.
CREATE OR REPLACE FUNCTION public.search_key(t text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path TO 'public', 'pg_temp'
AS $fn$
  SELECT lower(regexp_replace(public.unaccent('public.unaccent'::regdictionary, coalesce(t, '')),
                              '[^[:alnum:]]+', '', 'g'))
$fn$;

-- A pure function over its argument; nothing to protect, but Supabase grants
-- EXECUTE to anon/authenticated on new functions by default (20261013), and
-- the API calls it through its own pool. Keep the default surface small.
REVOKE ALL ON FUNCTION public.search_key(text) FROM PUBLIC, anon, authenticated;

-- CONCURRENTLY: must run OUTSIDE a transaction block (apply this file with
-- psql, not inside BEGIN/COMMIT). Does not block catalogue writes.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_category_items_search_key_trgm
  ON public.category_items
  USING gin (public.search_key(title || ' ' || category) gin_trgm_ops);
