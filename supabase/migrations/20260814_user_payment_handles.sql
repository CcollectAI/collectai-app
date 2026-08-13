-- Seller payment handles, so a settle-up link can carry the AMOUNT.
--
-- Why this exists
-- ---------------
-- `/p2p/payment-rails` shipped as a directory: it names rails and links to
-- their sites, but could not prefill anything, because `paypal.me/<handle>/
-- <amount>` needs the seller's handle and no column held one. Spec §5a already
-- permits the prefilled deep link — "a hyperlink is not payment initiation
-- under PSD2 Art. 4(15); the user's own PSP initiates the order" — so this was
-- a missing column, not a missing permission.
--
-- Why a table rather than a column on user_settings
-- -------------------------------------------------
--   1. A seller has MORE THAN ONE handle (PayPal and Revolut and Venmo), so a
--      single column would become a delimiter or a jsonb blob.
--   2. Access rules differ. `user_settings` is the member's own row; a payment
--      handle has to reach the COUNTERPARTY of an accepted trade, and only
--      them. Mixing the two means one policy guarding two sensitivity levels.
--   3. It is deletable on its own. A member removing a handle should not touch
--      their currency or region.
--
-- What it deliberately is NOT
-- ---------------------------
-- Not an account, not a credential, not a token. A handle is the public
-- identifier a stranger can already pay — `paypal.me/merle`. Sparrow still
-- never touches money, never learns whether payment happened, and never writes
-- a "paid" flag. Completion stays the two-sided human confirm.

CREATE TABLE IF NOT EXISTS public.user_payment_handles (
  user_id     uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  -- Matches a `key` in app/lib/payment_rails.py. Deliberately NOT an FK to a
  -- rails table: the rail list is code, reviewed as code, because its ORDER and
  -- its `reversible` flags are compliance-relevant and must not be editable by
  -- anything but a commit.
  rail_key    text        NOT NULL CHECK (rail_key = lower(rail_key) AND length(rail_key) BETWEEN 2 AND 32),
  -- The public identifier only. Bounded and stripped of the characters that
  -- would let one be pasted into a URL to mean something else.
  handle      text        NOT NULL CHECK (length(btrim(handle)) BETWEEN 2 AND 64),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, rail_key)
);

COMMENT ON TABLE public.user_payment_handles IS
  'Public payment identifiers a seller chooses to share, used only to build a '
  'prefilled deep link to the rail''s own site. Sparrow never holds funds, '
  'never learns whether payment occurred, and never writes a paid flag.';

ALTER TABLE public.user_payment_handles ENABLE ROW LEVEL SECURITY;

-- Owner-only through PostgREST. The counterparty NEVER reads this table
-- directly: the server resolves a seller's handle for a specific accepted
-- offer and returns a built link. A "counterparty can select" policy would let
-- anyone with a listing id enumerate handles, and a handle is the one piece of
-- this that follows the member off-platform.
DROP POLICY IF EXISTS user_payment_handles_owner_select ON public.user_payment_handles;
CREATE POLICY user_payment_handles_owner_select
  ON public.user_payment_handles FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS user_payment_handles_owner_write ON public.user_payment_handles;
CREATE POLICY user_payment_handles_owner_write
  ON public.user_payment_handles FOR ALL
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Same DEFAULT PRIVILEGES trap the matview swap hit on 2026-08-12: creating a
-- relation in this schema hands anon/authenticated a broad grant, and RLS is
-- the only thing standing behind it. Narrow the grant as well, so a policy
-- mistake is not a data leak on its own.
REVOKE ALL ON public.user_payment_handles FROM anon;
-- REVOKE first, then grant exactly four verbs. A bare GRANT here ADDS to what
-- DEFAULT PRIVILEGES already handed out, which on this schema included
-- TRUNCATE — and TRUNCATE BYPASSES ROW LEVEL SECURITY, so `authenticated`
-- would have been one call away from emptying a table RLS was the only guard
-- on. Verified on prod after applying: authenticated holds exactly
-- SELECT, INSERT, UPDATE, DELETE.
REVOKE ALL ON public.user_payment_handles FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_payment_handles TO authenticated;
