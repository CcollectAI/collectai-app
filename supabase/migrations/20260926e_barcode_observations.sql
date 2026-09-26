-- Learn barcodes from what members save (2026-09-26, Merle: no paid EAN source).
--
-- The catalogue holds 0 barcodes and the only free lookups are ISBN, so a LEGO
-- box or a Funko Pop never resolved (docs/BARCODE.md). And /intake/save
-- ACCEPTED a `barcode` field and threw it away. Now every save that came from
-- a scan records what the barcode turned out to be; the next scan of the same
-- code — by anyone — can use it (server/app/lib/barcode_learning.py).
--
-- One row per member per barcode: a member's later save replaces their own
-- answer, and "N members agree" is a count of rows. canonical_key is the BARE
-- catalogue item_key, resolved by the server from the title (never taken from
-- the client), with `category` beside it.
--
-- Server-only: written and read by the API as the table owner. RLS on with no
-- client policies, so PostgREST exposes nothing — plus the restrictive 2FA
-- policy every RLS table carries (20260926b; the watchdog checks it).

CREATE TABLE IF NOT EXISTS public.barcode_observations (
  barcode       text        NOT NULL,
  user_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  category      text,
  title         text        NOT NULL,
  canonical_key text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (barcode, user_id)
);

CREATE INDEX IF NOT EXISTS idx_barcode_observations_barcode
  ON public.barcode_observations (barcode);

ALTER TABLE public.barcode_observations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mfa_required ON public.barcode_observations;
CREATE POLICY mfa_required ON public.barcode_observations AS RESTRICTIVE FOR ALL TO authenticated
  USING ((SELECT public.mfa_satisfied())) WITH CHECK ((SELECT public.mfa_satisfied()));

REVOKE ALL ON public.barcode_observations FROM anon, authenticated;

COMMENT ON TABLE public.barcode_observations IS
  'What a scanned barcode turned out to be, one row per member (20260926e). Server-only.';
