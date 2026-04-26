-- Server-side dedup RPC for PostgREST writers (tcgcsv, discogs).
--
-- Background: market_hits is partitioned by seen_at (monthly) since 2026-04-19.
-- Postgres requires unique constraints on partitioned tables to include the
-- partition key, but seen_at = now() is unique per insert — defeating the
-- (provider, listing_id) dedup that the daily bulk feeds depend on.
-- PostgREST `?on_conflict=provider,listing_id` returns 42P10 because no such
-- constraint exists.
--
-- This RPC replaces the on_conflict round-trip with a set-based INSERT ...
-- WHERE NOT EXISTS, using the (provider, listing_id, seen_at) composite index's
-- leading columns for fast existence probes across partitions. Returns the
-- count of newly-inserted rows so the caller can track ingest stats.
--
-- See docs/DATA_SCALING_PLAN.md §10 + MEMORY task #17.

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

  WITH input AS (
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
    WHERE i.provider IS NOT NULL
      AND i.listing_id IS NOT NULL
      AND NOT EXISTS (
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

-- service_role + authenticated need EXECUTE so PostgREST can invoke via
-- POST /rest/v1/rpc/upsert_market_hits_batch
GRANT EXECUTE ON FUNCTION public.upsert_market_hits_batch(jsonb) TO service_role, authenticated;

COMMENT ON FUNCTION public.upsert_market_hits_batch(jsonb) IS
  'Idempotent batch INSERT into market_hits using WHERE NOT EXISTS. '
  'Replaces broken PostgREST ?on_conflict route since 2026-04-19 partitioning. '
  'Returns count of newly-inserted rows.';
