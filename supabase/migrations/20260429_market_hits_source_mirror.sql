-- Mirror provider → source + marketplace on market_hits insert paths.
-- Until 2026-04-29 every market_hits row had source = marketplace = NULL
-- because neither the asyncpg INSERT in marketplace_agent.py nor the
-- upsert_market_hits_batch RPC wrote those columns. Downstream filters
-- ("show me only ebay", intelligence/analytics queries) silently
-- matched zero rows.
--
-- Two-part fix: (1) the asyncpg INSERT now passes source + marketplace
-- explicitly (commit alongside this migration); (2) this migration
-- updates the bulk RPC to mirror provider into source + marketplace
-- so bulk-import pipelines (tcgcsv/pokemon/mtg/yugioh/discogs) don't
-- need caller changes.

CREATE OR REPLACE FUNCTION public.upsert_market_hits_batch(rows jsonb)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
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
      provider, source, marketplace,
      listing_id, title, price, currency, price_eur,
      condition, normalized_key, item_ref, category, url, image_url,
      features_json, is_listing, seen_at
    )
    SELECT
      i.provider, i.provider, i.provider,
      i.listing_id, i.title, i.price, i.currency, i.price_eur,
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
$function$;

-- One-time backfill: every existing NULL source/marketplace gets
-- mirrored from provider so historical filters work too.
UPDATE public.market_hits
   SET source = provider,
       marketplace = provider
 WHERE provider IS NOT NULL
   AND (source IS NULL OR marketplace IS NULL);
