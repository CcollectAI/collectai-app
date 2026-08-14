-- Delivery address for one accepted trade.
--
-- The logistics counterpart of `user_payment_handles`. Payments needed the
-- seller's handle before a link could carry the amount; carriage needs the
-- buyer's address before a shipment can be booked at all — and before PostNL's
-- tracking page can even be built, since it takes the recipient postcode.
--
-- Permitted explicitly by docs/P2P_MARKETPLACE_SPEC.md §5a:
--
--     We may                                    We may not
--     --------------------------------------    ------------------------------
--     Hand over addresses between parties       Generate labels under a Sparrow
--     after `accepted`                          carrier account — that makes us
--                                               the contracting party for
--                                               carriage
--
-- So this table exists to pass an address from one member to the other. Sparrow
-- does not book, does not insure, and still does not complete a trade from
-- carrier status.
--
-- PER OFFER, not per user
-- -----------------------
-- Data minimisation. An address is given FOR a specific trade with a specific
-- person, and dies with it: `ON DELETE CASCADE` from `p2p_offers` means
-- deleting the trade deletes the address, and the cascade from `auth.users`
-- means account deletion does too. A reusable "my addresses" book would keep
-- home addresses alive indefinitely for a feature that needs them for a week.
--
-- Before this table the app held NO postal address anywhere — verified against
-- the live schema 2026-08-14, where the only address-shaped column in `public`
-- was `beta_signups.ip_address`. That was a deliberate posture, and this is a
-- deliberate, bounded exception to it.

CREATE TABLE IF NOT EXISTS public.p2p_offer_addresses (
  offer_id       uuid        PRIMARY KEY REFERENCES public.p2p_offers(id) ON DELETE CASCADE,
  -- Denormalised so RLS can check ownership without joining the offer, and so
  -- the account-deletion cascade reaches this row directly.
  buyer_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  recipient_name text        NOT NULL CHECK (length(btrim(recipient_name)) BETWEEN 2 AND 120),
  line1          text        NOT NULL CHECK (length(btrim(line1)) BETWEEN 2 AND 200),
  line2          text        CHECK (line2 IS NULL OR length(btrim(line2)) <= 200),
  postcode       text        NOT NULL CHECK (length(btrim(postcode)) BETWEEN 2 AND 16),
  city           text        NOT NULL CHECK (length(btrim(city)) BETWEEN 1 AND 120),
  -- State / province. NULL-able because most of Europe has no such field, and
  -- REQUIRED for the US at the application layer — a US parcel without a state
  -- is undeliverable, while a Dutch one with a state field is a form asking a
  -- question with no answer. Enforcing "required for US" as a CHECK would bake
  -- one country's postal grammar into the schema; the router owns that.
  state          text        CHECK (state IS NULL OR length(btrim(state)) BETWEEN 2 AND 64),
  -- ISO 3166-1 alpha-2, upper-case. Constrained because it goes into PostNL's
  -- tracking URL as a path segment.
  country        text        NOT NULL CHECK (country ~ '^[A-Z]{2}$'),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.p2p_offer_addresses IS
  'Delivery address handed from buyer to seller for ONE accepted trade. '
  'Sparrow never books carriage, never insures a shipment, and never completes '
  'a trade from carrier status (P2P spec 5a). Dies with the offer.';

ALTER TABLE public.p2p_offer_addresses ENABLE ROW LEVEL SECURITY;

-- Buyer-only through PostgREST. The SELLER never reads this table directly —
-- the server hands the address over for a specific accepted offer, the same
-- shape as `user_payment_handles`. A "seller of the offer may select" policy
-- would be correct in principle and is deliberately not used: it puts a join
-- against p2p_offers inside a hot RLS predicate, and one wrong predicate there
-- exposes home addresses rather than, say, a price.
DROP POLICY IF EXISTS p2p_offer_addresses_buyer_select ON public.p2p_offer_addresses;
CREATE POLICY p2p_offer_addresses_buyer_select
  ON public.p2p_offer_addresses FOR SELECT
  USING (buyer_id = auth.uid());

DROP POLICY IF EXISTS p2p_offer_addresses_buyer_write ON public.p2p_offer_addresses;
CREATE POLICY p2p_offer_addresses_buyer_write
  ON public.p2p_offer_addresses FOR ALL
  USING (buyer_id = auth.uid())
  WITH CHECK (buyer_id = auth.uid());

-- REVOKE before GRANT: a bare GRANT ADDS to what this schema's DEFAULT
-- PRIVILEGES already handed out, which includes TRUNCATE — and TRUNCATE
-- BYPASSES ROW LEVEL SECURITY. That trap was found on user_payment_handles the
-- same day; it matters more here, where the rows are home addresses.
REVOKE ALL ON public.p2p_offer_addresses FROM anon;
REVOKE ALL ON public.p2p_offer_addresses FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.p2p_offer_addresses TO authenticated;
