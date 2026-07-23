-- Auto-create profiles row when a new user signs up.
--
-- Discovered 2026-05-25: no trigger existed on auth.users, so every signup
-- left the user without a profile. AuthProvider.loadProfile silently
-- swallowed the resulting "no rows" error and set profile=null, breaking
-- any UI that reads from profile (username display, account screen, etc.).
--
-- The function only inserts (id, created_at) — username stays null until
-- the user picks one (via onboarding or settings), avoiding any collision
-- logic and keeping the trigger fast.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, created_at)
  VALUES (NEW.id, NEW.created_at)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- Backfill for existing users (idempotent).
INSERT INTO public.profiles (id, created_at)
SELECT u.id, u.created_at
FROM auth.users u
LEFT JOIN public.profiles p ON p.id = u.id
WHERE p.id IS NULL
ON CONFLICT (id) DO NOTHING;
