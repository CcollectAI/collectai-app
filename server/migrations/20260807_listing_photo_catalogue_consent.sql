-- Marketplace photos may enrich the catalogue — but only with consent.
--
-- 54,115 of 221,391 `category_items` have no image. A member selling a real
-- copy photographs it, and that photo could fill the gap. Two reasons it cannot
-- simply be taken:
--
--   1. LICENCE. Terms of Service §3 granted a licence "solely to provide the
--      Service to you". Showing one member's photo to other members as
--      catalogue art is outside that. §3 now carries an explicit, opt-in,
--      revocable grant; this column is the record of that choice.
--
--   2. MISREPRESENTATION. The catalogue image is served as the FALLBACK on
--      other members' listings (`image_is_catalog`). Promote a photo of one
--      member's copy and it becomes the stand-in for a different copy in
--      different condition — the exact "a convenience becomes a
--      misrepresentation" risk already called out in ListingOut.image_is_catalog.
--
-- So consent is per LISTING (the moment the seller published that photo), not
-- per account, and it is revocable: clearing the flag must stop catalogue use.
BEGIN;

ALTER TABLE public.marketplace_listings
    ADD COLUMN IF NOT EXISTS photo_catalogue_consent boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.marketplace_listings.photo_catalogue_consent IS
    'Seller opted in to their listing photo being reused as catalogue art for '
    'the same product (ToS §3). Default FALSE — absence of a choice is not '
    'consent. Revocable: clearing it must stop catalogue use.';

-- Provenance on the catalogue side, so a member-contributed image is always
-- identifiable and can be withdrawn or audited. Without this a contributed
-- photo becomes indistinguishable from a licensed catalogue asset the moment
-- it lands, and "stop using my photo" becomes unanswerable.
ALTER TABLE public.category_items
    ADD COLUMN IF NOT EXISTS image_source text,
    ADD COLUMN IF NOT EXISTS image_contributed_by uuid,
    ADD COLUMN IF NOT EXISTS image_contributed_at timestamptz;

COMMENT ON COLUMN public.category_items.image_source IS
    'Where image_url came from. NULL = original catalogue import. '
    '''member_listing'' = contributed by a seller under ToS §3, with '
    'image_contributed_by/at recording who and when.';

-- Partial index: the withdrawal path ("stop using my photo") looks up by
-- contributor, and that is the only query shape that needs it. Justified per
-- governance rule 1 in docs/DATA_SCALING_PLAN.md (default = refuse to add):
-- no existing index covers image_contributed_by, and a seq scan over 221k rows
-- on a user-initiated privacy action is the wrong trade. Partial, so it indexes
-- only contributed rows rather than all 221k.
CREATE INDEX IF NOT EXISTS idx_category_items_contributed_by
    ON public.category_items (image_contributed_by)
    WHERE image_contributed_by IS NOT NULL;

COMMIT;
