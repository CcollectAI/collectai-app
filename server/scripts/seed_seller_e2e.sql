-- Seller-side E2E fixture (2026-08-15).
--
-- WHY: the account had FOUR offers and was the BUYER on every one, and zero
-- listings — so the entire sell side (accept, counter, take payment, book the
-- parcel, add tracking, confirm, rate the buyer) was unreachable by hand.
--
-- Three listings parked at three different stages, so every seller control is
-- on screen at once without having to drive a counterparty:
--
--   L1  pending    -> Accept / Counter / Decline
--   L2  accepted   -> How to pay / Book shipping / Add tracking / Mark sent
--   L3  completed  -> Rate the buyer   (both sides already confirmed)
--
-- Settlement stays OFF-PLATFORM by design (§5a): Sparrow links out to payment
-- rails and carriers and never holds funds, so "payment/logistics" here means
-- the settle sheet and the tracking block, not a money movement.
--
-- Everything is tagged for removal:
--   marketplace_listings.status_message = 'seed:seller-e2e'
--   p2p_offers.message LIKE '%[seed:seller-e2e]%'
-- Cleanup is at the bottom, commented out.

\set seller 'b4271bd3-b872-435c-a5f4-44d598f8d479'
\set buyer  '7db74bd9-7939-4929-afcf-473e76954af3'

BEGIN;

-- ── Listings ────────────────────────────────────────────────────────────────
-- marketplace_id is TEXT and 'sparrow' marks a NATIVE listing (§3: reuse this
-- table rather than adding one; external_listing_id/listing_url stay NULL).
INSERT INTO public.marketplace_listings
    (user_id, item_id, marketplace_id, listing_title, price, currency, format,
     status, condition_label, shipping_cost, status_message, listed_at, category)
SELECT :'seller'::uuid, i.id, 'sparrow', v.title, v.price, 'EUR', 'fixed_price',
       'active', v.cond, v.ship, 'seed:seller-e2e', now(), i.category
FROM (VALUES
  ('Solid Rage',                         'Solid Rage — Pokémon, near mint',            45.00, 'Near Mint', 3.95),
  ('Roronoa Zoro (035) [OP16] (Normal)', 'Roronoa Zoro OP16 035 — One Piece TCG',      25.00, 'Excellent', 3.95),
  ('One Piece, Vol. 1: Romance Dawn',    'One Piece Vol. 1: Romance Dawn — 1st print', 18.00, 'Good',      4.50)
) AS v(item_name, title, price, cond, ship)
JOIN public.items i
  ON i.user_id = :'seller'::uuid AND i.name = v.item_name AND NOT i.archived
WHERE NOT EXISTS (
  SELECT 1 FROM public.marketplace_listings ml
   WHERE ml.user_id = :'seller'::uuid AND ml.item_id = i.id
     AND ml.status_message = 'seed:seller-e2e'
);

-- ── The supply hook (§4) ────────────────────────────────────────────────────
-- Publishing a listing writes a market_hits row so the listing feeds demand /
-- Target Hit like any other supply. is_listing = TRUE: it is an asking price,
-- not a sold comp, and valuation must keep ignoring it.
INSERT INTO public.market_hits
    (provider, listing_id, title, price_eur, currency, condition,
     item_ref, normalized_key, category, url, seen_at, is_listing)
SELECT 'sparrow', ml.id::text, ml.listing_title, ml.price, 'EUR', ml.condition_label,
       i.category || ':' || COALESCE(i.canonical_key, i.id::text),
       COALESCE(i.canonical_key, i.id::text), i.category,
       'sparrow://listing/' || ml.id::text, now(), TRUE
FROM public.marketplace_listings ml
JOIN public.items i ON i.id = ml.item_id
WHERE ml.status_message = 'seed:seller-e2e'
  AND i.category IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.market_hits mh
     WHERE mh.provider = 'sparrow' AND mh.listing_id = ml.id::text
  );

-- ── L1: a fresh offer awaiting your decision ────────────────────────────────
INSERT INTO public.p2p_offers
    (listing_id, buyer_id, seller_id, amount, currency, status, message, counter_count, created_at)
SELECT ml.id, :'buyer'::uuid, :'seller'::uuid, 38.00, 'EUR', 'pending',
       'Would you take 38? [seed:seller-e2e]', 0, now() - interval '2 hours'
FROM public.marketplace_listings ml
WHERE ml.status_message = 'seed:seller-e2e' AND ml.price = 45.00
  AND NOT EXISTS (SELECT 1 FROM public.p2p_offers o WHERE o.listing_id = ml.id);

-- ── L2: accepted — payment + logistics stage ────────────────────────────────
INSERT INTO public.p2p_offers
    (listing_id, buyer_id, seller_id, amount, currency, status, message, counter_count, created_at)
SELECT ml.id, :'buyer'::uuid, :'seller'::uuid, 22.00, 'EUR', 'accepted',
       'Deal! [seed:seller-e2e]', 1, now() - interval '1 day'
FROM public.marketplace_listings ml
WHERE ml.status_message = 'seed:seller-e2e' AND ml.price = 25.00
  AND NOT EXISTS (SELECT 1 FROM public.p2p_offers o WHERE o.listing_id = ml.id);

-- The buyer has already supplied a delivery address on the accepted one, so
-- the seller side has something to post to and PostNL tracking can resolve.
INSERT INTO public.p2p_offer_addresses
    (offer_id, buyer_id, recipient_name, line1, postcode, city, country)
SELECT o.id, o.buyer_id, 'Test Buyer', 'Keizersgracht 123', '1015 CJ', 'Amsterdam', 'NL'
FROM public.p2p_offers o
JOIN public.marketplace_listings ml ON ml.id = o.listing_id
WHERE ml.status_message = 'seed:seller-e2e' AND o.status = 'accepted'
  AND NOT EXISTS (SELECT 1 FROM public.p2p_offer_addresses a WHERE a.offer_id = o.id);

-- ── L3: completed — ready to rate ───────────────────────────────────────────
INSERT INTO public.p2p_offers
    (listing_id, buyer_id, seller_id, amount, currency, status, message, counter_count,
     seller_confirmed_at, buyer_confirmed_at, tracking_carrier, tracking_code, tracking_set_at, created_at)
SELECT ml.id, :'buyer'::uuid, :'seller'::uuid, 15.00, 'EUR', 'completed',
       'Thanks! [seed:seller-e2e]', 0,
       now() - interval '3 days', now() - interval '1 day',
       'postnl', '3STBJG4471200099', now() - interval '4 days', now() - interval '6 days'
FROM public.marketplace_listings ml
WHERE ml.status_message = 'seed:seller-e2e' AND ml.price = 18.00
  AND NOT EXISTS (SELECT 1 FROM public.p2p_offers o WHERE o.listing_id = ml.id);

COMMIT;

\echo '=== what you should now see under Selling ==='
SELECT ml.listing_title, ml.price AS asking, o.amount AS offered, o.status,
       (a.offer_id IS NOT NULL) AS has_address, o.tracking_code
FROM public.marketplace_listings ml
LEFT JOIN public.p2p_offers o ON o.listing_id = ml.id
LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
WHERE ml.status_message = 'seed:seller-e2e'
ORDER BY ml.price DESC;

-- CLEANUP (run by hand when done):
--   DELETE FROM public.p2p_offer_addresses WHERE offer_id IN (
--     SELECT o.id FROM public.p2p_offers o JOIN public.marketplace_listings ml ON ml.id=o.listing_id
--     WHERE ml.status_message='seed:seller-e2e');
--   DELETE FROM public.p2p_offers WHERE message LIKE '%[seed:seller-e2e]%';
--   DELETE FROM public.market_hits WHERE provider='sparrow' AND listing_id IN (
--     SELECT id::text FROM public.marketplace_listings WHERE status_message='seed:seller-e2e');
--   DELETE FROM public.marketplace_listings WHERE status_message='seed:seller-e2e';
