CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  ref_code TEXT;
  uname    TEXT;
BEGIN
  -- NULLIF collapses '' (user tabbed through the optional field) to NULL so it
  -- does not read as an attributed signup.
  ref_code := NULLIF(UPPER(TRIM(COALESCE(NEW.raw_user_meta_data->>'referral_code', ''))), '');

  -- Username, added 2026-07-24. Previously the ONLY writer was a client-side
  -- upsert in app/(auth)/register.tsx. RLS on profiles requires
  -- auth.uid() = id for INSERT/UPDATE, but on the email-verification signup
  -- path signUp() returns a user with NO session, so auth.uid() is NULL and
  -- that upsert is always rejected. register.tsx only console.warn'd and
  -- continued -- and warn is stripped in TestFlight -- so it failed invisibly:
  -- 0 of 23 profiles had a username, display_name or avatar. Every social
  -- surface (chat inbox, public profile, event "Hosted by", leaderboard)
  -- therefore rendered "Unknown".
  --
  -- Reading it here instead works because this trigger is SECURITY DEFINER,
  -- so RLS does not apply -- exactly how referral_code above already works.
  uname := NULLIF(TRIM(COALESCE(NEW.raw_user_meta_data->>'username', '')), '');

  -- A duplicate username must never abort signup. This trigger runs inside the
  -- auth.users INSERT, so an unhandled unique_violation on
  -- profiles_username_key would fail account creation outright. Drop the name
  -- and let the user pick one later instead.
  IF uname IS NOT NULL AND EXISTS (
       SELECT 1 FROM public.profiles p WHERE lower(p.username) = lower(uname)
     ) THEN
    uname := NULL;
  END IF;

  BEGIN
    INSERT INTO public.profiles (id, created_at, referred_by_code, username, display_name)
    VALUES (NEW.id, NEW.created_at, ref_code, uname, uname)
    ON CONFLICT (id) DO UPDATE
      -- Attribution is set once and must never be overwritten by a later write.
      SET referred_by_code = COALESCE(public.profiles.referred_by_code, EXCLUDED.referred_by_code),
          username         = COALESCE(public.profiles.username,         EXCLUDED.username),
          display_name     = COALESCE(public.profiles.display_name,     EXCLUDED.display_name);
  EXCEPTION WHEN unique_violation THEN
    -- Lost a race for the same username between the EXISTS check and the
    -- INSERT. Fall back to a nameless profile rather than failing signup.
    INSERT INTO public.profiles (id, created_at, referred_by_code)
    VALUES (NEW.id, NEW.created_at, ref_code)
    ON CONFLICT (id) DO UPDATE
      SET referred_by_code = COALESCE(public.profiles.referred_by_code, EXCLUDED.referred_by_code);
  END;

  RETURN NEW;
END;
$fn$;
