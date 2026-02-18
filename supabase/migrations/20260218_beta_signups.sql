-- ============================================================================
-- Migration: 20260218_beta_signups.sql
-- Purpose:   Create the beta_signups table for pre-launch email collection.
--            Anonymous signups — no FK to auth.users.
-- Safe:      Uses IF NOT EXISTS / DO $$ policy guard throughout.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. BETA_SIGNUPS — pre-launch email waitlist
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.beta_signups (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  email           text        NOT NULL UNIQUE,
  referral_source text,
  ip_address      text,
  signed_up_at    timestamptz NOT NULL DEFAULT now()
);

-- email already has a UNIQUE constraint (implicit index), no separate index needed

CREATE INDEX IF NOT EXISTS idx_beta_signups_signed_up_at
  ON public.beta_signups(signed_up_at DESC);

ALTER TABLE public.beta_signups ENABLE ROW LEVEL SECURITY;

-- Deny all direct access — backend pool bypasses RLS
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'beta_signups' AND policyname = 'beta_signups_deny_all'
  ) THEN
    CREATE POLICY beta_signups_deny_all ON public.beta_signups
      USING (false);
  END IF;
END $$;

COMMIT;
