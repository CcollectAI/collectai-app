-- 2026-09-18: one name for the Sparrow marketplace.
--
-- `p2p_listing_router` writes `marketplace_id = 'sparrow'` — all 7 listings on
-- production carry it — while `marketplace_fee_schedules` keyed the same
-- marketplace **'collectai'**, the pre-rename brand (CollectAI -> Sparrow
-- Collect, 2026-05-04), and so did the server's VALID_MARKETPLACES and the
-- client's MarketplaceId union.
--
-- Nothing broke, by luck: `MARKETPLACE_CONFIG['sparrow']` was undefined and the
-- `?? MARKETPLACE_CONFIG.collectai` fallback rendered the right label for the
-- wrong reason. What it DID cost: a fee lookup keyed on the listing's
-- marketplace could never match the schedule, and a PATCH validating
-- `marketplace_id` would have rejected every row the live P2P flow has written.
--
-- 'sparrow' is canonical because it is the brand AND the value the database
-- already holds. 'collectai' appears in 0 listing rows, so there is no data to
-- migrate on that side — only this schedule key.
--
-- APPLIED to production 2026-09-18. Verified after: 0 listings whose
-- marketplace_id has no matching fee schedule.

BEGIN;

UPDATE public.marketplace_fee_schedules
   SET marketplace_id = 'sparrow',
       display_name   = 'Sparrow P2P'
 WHERE marketplace_id = 'collectai';

DO $$
DECLARE orphans int;
BEGIN
  SELECT count(*) INTO orphans
    FROM public.marketplace_listings l
   WHERE NOT EXISTS (SELECT 1 FROM public.marketplace_fee_schedules f
                      WHERE f.marketplace_id = l.marketplace_id);
  IF orphans > 0 THEN
    RAISE EXCEPTION 'listings with no matching fee schedule: %', orphans;
  END IF;
END $$;

COMMIT;
