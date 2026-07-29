-- v_offer_summary_v1: expose the fields the Deal Desk API actually renders.
--
-- _row_to_offer_summary() in deal_desk_router.py reads item_id, item_title,
-- item_image_url, current_price, currency, buyer_name/seller_name and
-- buyer_avatar_url/seller_avatar_url. The view exposed NONE of those names —
-- it had listing_title / listing_image_url / listing_price / listing_currency
-- and no item or profile columns at all.
--
-- Every dict.get() therefore fell to its default, so an offer card rendered:
--   item_title    "Untitled"
--   current_price 0            (the offer was 210)
--   other_user    "Unknown"
--   item_id       ""           (so "view item" from an offer had no target)
-- Verified 2026-07-29 by seeding a pending offer and reading /deals/active.
--
-- The mapper is being fixed to read the listing_* names it already had; this
-- migration adds the three things the view genuinely could not supply:
-- the underlying item_id, and the two parties' display names / avatars.
--
-- profiles.id is the auth user id, so it joins straight onto seller_id/buyer_id.

CREATE OR REPLACE VIEW public.v_offer_summary_v1 AS
SELECT
    o.id,
    o.id AS offer_id,
    o.listing_id,
    o.seller_id,
    o.buyer_id,
    o.amount,
    o.status,
    o.message,
    o.counter_count,
    o.expires_at,
    o.created_at,
    o.updated_at,
    l.title      AS listing_title,
    l.image_url  AS listing_image_url,
    l.price      AS listing_price,
    l.currency   AS listing_currency,
    -- new: the item behind the listing, so an offer can deep-link to it
    l.item_id    AS item_id,
    -- new: who the other party is, without a second round trip
    sp.display_name  AS seller_name,
    sp.username      AS seller_username,
    sp.avatar_url    AS seller_avatar_url,
    bp.display_name  AS buyer_name,
    bp.username      AS buyer_username,
    bp.avatar_url    AS buyer_avatar_url
FROM offers o
JOIN listings l ON l.id = o.listing_id
LEFT JOIN profiles sp ON sp.id = o.seller_id
LEFT JOIN profiles bp ON bp.id = o.buyer_id;
