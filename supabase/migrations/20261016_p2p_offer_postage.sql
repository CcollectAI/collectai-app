-- Postage is part of the deal, the way Vinted shows it (2026-10-16).
--
-- Walked as a buyer: a listing at EUR 20 + EUR 2,50 postage; the offer, the
-- counter, "Pay the seller" (Agreed amount EUR 19), the buyer's new item
-- (purchase price 19) and the seller's sale (net 22,50 - postage) all carried
-- the ITEM amount only. The listing's postage reached nothing after the listing
-- page. Vinted: an offer is on the item only, postage cannot be negotiated and
-- is added on top, and the buyer sees item + postage = total before paying.
--
-- p2p_offers.shipping_cost  — the listing's postage SNAPSHOTTED when the offer
--   is made: what the buyer saw when they bid. A seller editing the listing
--   afterwards must not change an agreed trade. NULL = the seller stated none
--   (agree it in chat), never 0.
-- marketplace_sales.shipping_charged — what the buyer paid the seller for
--   postage. The seller's net is sale_price + shipping_charged - fees - their
--   actual postage, so a reimbursed stamp no longer reads as a loss.
--
-- Open offers take the listing's CURRENT postage (it is what their buyer sees
-- today); finished ones stay NULL — nobody can say now what was agreed.
ALTER TABLE public.p2p_offers
  ADD COLUMN IF NOT EXISTS shipping_cost numeric(12,2)
  CHECK (shipping_cost IS NULL OR shipping_cost >= 0);

ALTER TABLE public.marketplace_sales
  ADD COLUMN IF NOT EXISTS shipping_charged numeric(12,2)
  CHECK (shipping_charged IS NULL OR shipping_charged >= 0);

UPDATE public.p2p_offers o
   SET shipping_cost = round(l.shipping_cost::numeric, 2)
  FROM public.marketplace_listings l
 WHERE l.id = o.listing_id
   AND o.shipping_cost IS NULL
   AND l.shipping_cost IS NOT NULL
   AND o.status IN ('pending', 'countered', 'accepted', 'shipped');
