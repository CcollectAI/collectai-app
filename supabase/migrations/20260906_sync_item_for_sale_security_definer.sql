-- GoTrue could not delete any user who owned a marketplace listing.
--
-- Symptom since at least 2026-08-30: DELETE /auth/v1/admin/users/{id} returns
-- 500 "Database error deleting user", the Postgres log says
-- `permission denied for table marketplace_listings`, sanity-e2e is red on
-- every push, and the Supabase dashboard's own user delete fails identically.
--
-- THE CHAIN
--   1. GoTrue deletes auth.users AS `supabase_auth_admin`.
--   2. marketplace_listings.user_id REFERENCES auth.users ON DELETE CASCADE,
--      so the cascade deletes that user's listings.
--   3. trg_sync_item_for_sale fires AFTER DELETE on marketplace_listings.
--   4. sync_item_for_sale() was SECURITY INVOKER, so it ran as
--      supabase_auth_admin, and its body does
--          SELECT count(*) FROM public.marketplace_listings ...
--      on which that role holds NO grants. The error therefore names the table
--      the TRIGGER READS, not the table the cascade deletes — which is why it
--      looked like a cascade-privilege problem for a week.
--
-- Evidence before the fix:
--   * Of 24 synthetic accounts deleted 2026-09-06, 20 succeeded and 4 failed —
--     exactly the 4 owning marketplace_listings rows (3, 6, 6, 7).
--   * Controlled before/after on one user: 500 with 6 listings present; delete
--     those 6 rows; the identical call returns 200.
--
-- Two wrong turns worth remembering:
--   * "supabase_auth_admin has DELETE on none of the 44 FK tables" is true and
--     IRRELEVANT — a cascade only needs privileges on tables that HAVE ROWS,
--     which is why 20 accounts owning nothing deleted fine.
--   * GRANT DELETE ON marketplace_listings TO supabase_auth_admin was applied
--     and TESTED: still 500. Wrong privilege (SELECT is what the trigger
--     needs) and wrong statement. Reverted; prod returned to baseline.
--
-- THE FIX, and why it is not a bare ALTER ... SECURITY DEFINER.
--
-- Running as the owner is correct for a trigger maintaining a derived column:
-- it must not depend on the caller's grants. But SECURITY DEFINER also removes
-- the RLS filter that was quietly containing a separate weakness:
--
--     marketplace_listings INSERT policy is WITH CHECK (auth.uid() = user_id)
--
-- which constrains who owns the LISTING and says nothing about item_id. A user
-- can already insert a listing pointing at someone else's item. Today the
-- trigger's UPDATE runs as the invoker, so items' RLS silently no-ops that
-- cross-user write. A bare SECURITY DEFINER would make it succeed — letting
-- anyone flip another member's items.for_sale by referencing their item id.
--
-- So the UPDATEs are scoped to items belonging to the listing's own user.
-- Verified behaviour-preserving before applying: of 8 live listings, 0 have a
-- missing item and 0 have an owner mismatch.
--
-- search_path is pinned: SECURITY DEFINER without it is a privilege-escalation
-- vector (a caller-controlled search_path can shadow public.marketplace_listings)
-- and Supabase's own linter flags it.
--
-- NOT done here, deliberately: constraining item_id to items you own at the
-- table level. That is the real structural fix, it could reject existing rows,
-- and it deserves its own pass rather than riding along with a hotfix.
--
-- Reversible: restore the previous body and ALTER ... SECURITY INVOKER.

CREATE OR REPLACE FUNCTION public.sync_item_for_sale()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = public, pg_temp
AS $function$
DECLARE
    target_item uuid;
    owner_id    uuid;
    live_count  integer;
BEGIN
    -- On DELETE only OLD is populated; on INSERT only NEW. On an UPDATE that
    -- MOVES a listing between items (not a thing today, but the trigger must
    -- not silently strand the old item as for_sale), both need recomputing.
    target_item := COALESCE(NEW.item_id, OLD.item_id);
    owner_id    := COALESCE(NEW.user_id, OLD.user_id);
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
    --
    -- `user_id = owner_id` replaces the RLS filter this function lost by
    -- becoming SECURITY DEFINER. Without it, a listing pointing at another
    -- member's item would flip THEIR for_sale flag.
    UPDATE public.items
       SET for_sale = (live_count > 0)
     WHERE id = target_item
       AND user_id = owner_id
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
           AND user_id = COALESCE(OLD.user_id, owner_id)
           AND COALESCE(for_sale, FALSE) IS DISTINCT FROM (live_count > 0);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$function$;
