-- Fix within-batch dedup in upsert_market_hits_batch.
--
-- Problem: the previous version of the RPC (20260426) used
--   INSERT ... SELECT ... FROM input WHERE NOT EXISTS (... market_hits ...)
-- which only deduplicated against market_hits. If the same input batch
-- contained the same (provider, listing_id) twice (which the discogs
-- pipeline does on retries / pagination overlap), both rows passed
-- WHERE NOT EXISTS, both got the same `now()` (single statement → single
-- now()), and the unique constraint on
-- (provider, listing_id, seen_at) rejected the second row. Because INSERT
-- is one atomic statement, the WHOLE 100-row batch rolled back, producing
-- the "Persisted 0/N hits" silent-fail signature in bake.log.
--
-- Verified 2026-05-02:
--   - every successful discogs row has a unique listing_id (no across-batch dups)
--   - all listing_ids that hit 23505 are MISSING from market_hits
--   - at 19:58:41.593482 UTC 18 different rows landed at the same microsecond
--     (one batch, one now())
--
-- Fix: deduplicate the input batch by (provider, listing_id) before INSERT
-- using DISTINCT ON. Across-batch duplicates are still allowed (different
-- now() per call) and the WHERE NOT EXISTS still catches "this listing
-- already exists in market_hits".
--
-- Pure RPC body change. No schema migration. No bake restart needed.

CREATE OR REPLACE FUNCTION public.upsert_market_hits_batch(rows jsonb)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  inserted_count integer;
BEGIN
  IF rows IS NULL OR jsonb_typeof(rows) <> 'array' OR jsonb_array_length(rows) = 0 THEN
    RETURN 0;
  END IF;

  WITH input_raw AS (
    SELECT * FROM jsonb_to_recordset(rows) AS x(
      provider       text,
      listing_id     text,
      title          text,
      price          numeric,
      currency       text,
      price_eur      numeric,
      condition      text,
      normalized_key text,
      item_ref       text,
      category       text,
      url            text,
      image_url      text,
      features_json  jsonb,
      is_listing     boolean
    )
  ),
  -- Within-batch dedup: keep one row per (provider, listing_id). Pickng
  -- arbitrary ordering for the surviving row is fine — duplicate listings
  -- in a single batch carry the same payload, so any of them works.
  input AS (
    SELECT DISTINCT ON (provider, listing_id) *
    FROM input_raw
    WHERE provider IS NOT NULL
      AND listing_id IS NOT NULL
  ),
  inserted AS (
    INSERT INTO public.market_hits (
      provider, listing_id, title, price, currency, price_eur,
      condition, normalized_key, item_ref, category, url, image_url,
      features_json, is_listing, seen_at
    )
    SELECT
      i.provider, i.listing_id, i.title, i.price, i.currency, i.price_eur,
      i.condition, i.normalized_key, i.item_ref, i.category, i.url, i.image_url,
      COALESCE(i.features_json, '{}'::jsonb),
      COALESCE(i.is_listing, false),
      now()
    FROM input i
    WHERE NOT EXISTS (
      SELECT 1 FROM public.market_hits mh
      WHERE mh.provider = i.provider
        AND mh.listing_id = i.listing_id
    )
    RETURNING 1
  )
  SELECT COUNT(*) INTO inserted_count FROM inserted;

  RETURN COALESCE(inserted_count, 0);
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_market_hits_batch(jsonb) TO service_role, authenticated;

COMMENT ON FUNCTION public.upsert_market_hits_batch(jsonb) IS
  'Idempotent batch INSERT into market_hits using WHERE NOT EXISTS. '
  'Includes within-batch dedup via DISTINCT ON to prevent atomic-INSERT '
  'rollback when a single batch contains duplicate (provider, listing_id). '
  'Returns count of newly-inserted rows.';
