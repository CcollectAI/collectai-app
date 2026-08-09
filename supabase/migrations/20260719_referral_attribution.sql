-- Referral attribution: carry a creator's code from signup onto the profile.
--
-- Context: the creator-growth program pays micro-influencers a commission on
-- the Pro subscriptions they drive. Before this migration there was no path by
-- which a code from a creator's bio could reach a user record — the landing
-- page dropped `?ref=`, the deep-link handler read only URL fragments, and
-- signUp() passed no metadata.
--
-- The chain this closes:
--   register screen  → supabase.auth.signUp({ options: { data: { referral_code } } })
--                    → auth.users.raw_user_meta_data->>'referral_code'
--                    → (this trigger)
--                    → public.profiles.referred_by_code
--
-- Deliberately NOT a foreign key to public.creators: that table is owned by the
-- admin dashboard's own migration set (collectai-admin/supabase/migrations/
-- 001_kpi_tables.sql) and may be applied before or after this file. A soft
-- reference keeps the two sets independent; an unknown code is recorded rather
-- than rejected, which is also what we want for attribution (a typo'd code
-- should not block a signup).

-- ─── Column ─────────────────────────────────────────────────────────────────

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS referred_by_code TEXT;

COMMENT ON COLUMN public.profiles.referred_by_code IS
  'Creator affiliate_code this user signed up under. Soft reference to public.creators.affiliate_code. Normalised to upper-case, set once at signup.';

-- Attribution queries group by this column; keep it cheap. Partial, because
-- the overwhelming majority of rows are organic (NULL).
CREATE INDEX IF NOT EXISTS idx_profiles_referred_by_code
  ON public.profiles (referred_by_code)
  WHERE referred_by_code IS NOT NULL;

-- ─── Trigger ────────────────────────────────────────────────────────────────
-- Extends 20260525_handle_new_user_trigger.sql. Still only touches columns it
-- owns, so it stays fast and collision-free; username is still left to
-- onboarding.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  ref_code TEXT;
BEGIN
  -- NULLIF collapses '' (user tabbed through the optional field) to NULL so it
  -- does not read as an attributed signup.
  ref_code := NULLIF(UPPER(TRIM(COALESCE(NEW.raw_user_meta_data->>'referral_code', ''))), '');

  INSERT INTO public.profiles (id, created_at, referred_by_code)
  VALUES (NEW.id, NEW.created_at, ref_code)
  ON CONFLICT (id) DO UPDATE
    -- The client also upserts the profile (register.tsx) and can win the race.
    -- Only fill the code when it is still empty: attribution is set once and
    -- must never be overwritten by a later profile write.
    SET referred_by_code = COALESCE(public.profiles.referred_by_code, EXCLUDED.referred_by_code);

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- ─── Backfill ───────────────────────────────────────────────────────────────
-- Existing users signed up before referral capture existed, but a code may sit
-- in their auth metadata if they registered from a build that already sent it.

UPDATE public.profiles p
SET referred_by_code = NULLIF(UPPER(TRIM(u.raw_user_meta_data->>'referral_code')), '')
FROM auth.users u
WHERE u.id = p.id
  AND p.referred_by_code IS NULL
  AND NULLIF(TRIM(COALESCE(u.raw_user_meta_data->>'referral_code', '')), '') IS NOT NULL;
