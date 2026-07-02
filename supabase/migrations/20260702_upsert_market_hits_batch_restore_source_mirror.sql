-- Restore the provider->source/marketplace mirror in upsert_market_hits_batch.
--
-- REGRESSION: 20260429_market_hits_source_mirror.sql updated this RPC to set
-- source = marketplace = provider on insert. Then 20260502_upsert_market_hits_
-- batch_dedup_within_batch.sql recreated the function to add within-batch dedup
-- but its INSERT column list DROPPED source + marketplace. So since 2026-05-02
-- every RPC-inserted row (tcgcsv, discogs) has source = marketplace = NULL
-- again — ~40% of daily market_hits inserts. Found in the 2026-07-02 silent-
-- failure sweep (3.5M null-source rows in the 90d window).
--
-- This version = 20260502 (dedup) + the 20260429 source mirror, carried
-- forward together. Pure RPC body change: signature unchanged (rpc.lock
-- unaffected), no schema migration, no bake restart needed. Importers already
-- send `provider` — nothing changes on the writer side.
--
-- Existing NULL rows are intentionally NOT backfilled: a 3.5M-row UPDATE on the
-- partitioned market_hits is the documented IO-killer, and these rows age out
-- of the 90d window (and drop with their partitions) anyway. Forward-fix only.

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
  -- Within-batch dedup: keep one row per (provider, listing_id) (20260502).
  input AS (
    SELECT DISTINCT ON (provider, listing_id) *
    FROM input_raw
    WHERE provider IS NOT NULL
      AND listing_id IS NOT NULL
  ),
  inserted AS (
    INSERT INTO public.market_hits (
      provider, source, marketplace, listing_id, title, price, currency, price_eur,
      condition, normalized_key, item_ref, category, url, image_url,
      features_json, is_listing, seen_at
    )
    SELECT
      -- source + marketplace mirror provider (restored from 20260429).
      i.provider, i.provider, i.provider,
      i.listing_id, i.title, i.price, i.currency, i.price_eur,
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
  'Idempotent batch INSERT into market_hits (WHERE NOT EXISTS) with within-batch '
  'DISTINCT ON dedup AND provider->source/marketplace mirror. Returns count of '
  'newly-inserted rows.';
