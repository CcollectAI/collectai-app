-- Keep items.for_sale in sync with whether the item has a live P2P listing.
--
-- THE BUG (measured against prod, 2026-08-08, both directions)
-- -----------------------------------------------------------------------------
-- Three code paths change a listing's live-ness, and NONE of them touched the
-- items row that the collection UI reads:
--
--   1. POST /p2p/listings with item_id       (SellOnSparrowSection — list from
--      your collection)                       -> for_sale stayed FALSE
--   2. POST /p2p/listings/{id}/delist        (Mark as sold)
--                                             -> for_sale stayed whatever it was
--   3. POST /p2p/offers/{id}/confirm         (two-sided completion)
--                                             -> same
--
-- Only the marketplace-only create path set it, on INSERT, and never cleared it.
-- Proved end-to-end through the live API:
--
--   list a collection item  -> listing active, items.for_sale = f   (wrong)
--   mark that listing sold  -> listing sold,   items.for_sale = f
--   marketplace-only create -> items.for_sale = t
--   mark THAT sold          -> listing sold,   items.for_sale = t   (wrong)
--
-- It is not cosmetic. `items.for_sale` drives:
--   * src/hooks/useItemDetail.ts:163 -> the "Listed" badge on item detail. A
--     seller listing from their collection got NO badge, so their own item gave
--     them no evidence it was listed — the exact condition under which someone
--     lists again, which then 409s as ALREADY_LISTED and reads as a broken app.
--   * items_export_router.py:334 -> the `for_sale` column in the CSV export,
--     which was simply wrong in both directions.
--
-- WHY A TRIGGER AND NOT THREE PATCHES
-- -----------------------------------------------------------------------------
-- This is an instance of a CLASS, so it gets a chokepoint, not N call-site
-- fixes (learning_enumerate_mechanically_never_triage_by_judgment). Three
-- writers exist TODAY; the fourth is the one that would silently reintroduce
-- this. A trigger on the listings table cannot be bypassed by a new endpoint, a
-- backfill script, or a manual UPDATE during an incident.
--
-- It also derives rather than duplicates: for_sale becomes a cache of "does a
-- live listing exist", recomputed from the listings table itself, so the two
-- cannot disagree.
--
-- SCOPE — deliberately narrow
-- -----------------------------------------------------------------------------
-- Only `marketplace_id = 'sparrow'` rows. `marketplace_listings` also holds
-- rows for external marketplaces, and an eBay listing is NOT a reason to show
-- the Sparrow "Listed" badge or to let deal-desk treat the item as ours to sell.
--
-- `asking_price` is deliberately NOT touched. It belongs to deal_desk's
-- PUT /items/{id}/for-sale (an "open to offers" asking price the owner sets
-- independently), and the badge already renders correctly without it ("Listed"
-- with no figure). Overwriting a user-entered number from a listing price would
-- be this same bug with the arrow reversed.

CREATE OR REPLACE FUNCTION public.sync_item_for_sale()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_item uuid;
    live_count  integer;
BEGIN
    -- On DELETE only OLD is populated; on INSERT only NEW. On an UPDATE that
    -- MOVES a listing between items (not a thing today, but the trigger must
    -- not silently strand the old item as for_sale), both need recomputing.
    target_item := COALESCE(NEW.item_id, OLD.item_id);
    IF target_item IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT count(*) INTO live_count
      FROM public.marketplace_listings l
     WHERE l.item_id = target_item
       AND l.marketplace_id = 'sparrow'
       AND l.status = 'active'
       AND l.delisted_at IS NULL;

    -- Recomputed from the table rather than toggled from the transition, so a
    -- second live listing on the same item cannot leave for_sale FALSE when one
    -- of them sells. The WHERE guard makes this a no-op write when nothing
    -- changed, which keeps it off items' updated_at and out of any change feed.
    UPDATE public.items
       SET for_sale = (live_count > 0)
     WHERE id = target_item
       AND COALESCE(for_sale, FALSE) IS DISTINCT FROM (live_count > 0);

    -- Handle a listing that moved between items: settle the OLD one too.
    IF TG_OP = 'UPDATE' AND OLD.item_id IS NOT NULL
       AND OLD.item_id IS DISTINCT FROM NEW.item_id THEN
        SELECT count(*) INTO live_count
          FROM public.marketplace_listings l
         WHERE l.item_id = OLD.item_id
           AND l.marketplace_id = 'sparrow'
           AND l.status = 'active'
           AND l.delisted_at IS NULL;
        UPDATE public.items
           SET for_sale = (live_count > 0)
         WHERE id = OLD.item_id
           AND COALESCE(for_sale, FALSE) IS DISTINCT FROM (live_count > 0);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_item_for_sale ON public.marketplace_listings;

-- AFTER, so it observes the committed row state the recompute reads. Fires on
-- DELETE too: test cleanup and moderation removal both delete listings, and
-- leaving for_sale TRUE there is the same lie.
CREATE TRIGGER trg_sync_item_for_sale
AFTER INSERT OR UPDATE OR DELETE ON public.marketplace_listings
FOR EACH ROW
EXECUTE FUNCTION public.sync_item_for_sale();

-- Backfill. Every existing row is wrong in one direction or the other, and
-- without this the trigger only fixes items that happen to be touched again.
-- Restricted to items that HAVE a sparrow listing, so it cannot clear the flag
-- on items where deal_desk's toggle set it for its own reasons.
UPDATE public.items i
   SET for_sale = EXISTS (
         SELECT 1 FROM public.marketplace_listings l
          WHERE l.item_id = i.id
            AND l.marketplace_id = 'sparrow'
            AND l.status = 'active'
            AND l.delisted_at IS NULL)
 WHERE EXISTS (
         SELECT 1 FROM public.marketplace_listings l2
          WHERE l2.item_id = i.id
            AND l2.marketplace_id = 'sparrow');
