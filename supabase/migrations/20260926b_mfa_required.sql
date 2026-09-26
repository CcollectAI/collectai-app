-- Second factor enforced by the DATABASE, not only by the app (2026-09-26).
--
-- The app sends an aal1 session (password, no code yet) to the code screen,
-- but PostgREST accepted that token: anyone with a member's password could
-- read and write their rows with the anon key + the aal1 JWT, never touching
-- the code. Merle's call: fix it (docs/OPEN_DECISIONS.md #5).
--
-- The rule, identical to server/app/auth.py::_require_second_factor:
--   a request is allowed when its JWT is aal2, OR the member has no VERIFIED
--   factor. Members without 2FA are untouched (measured 2026-09-26: exactly
--   one account in prod has a verified factor — the throwaway zz-lifecycle).
--
-- HOW: one RESTRICTIVE policy per RLS-enabled public table, TO authenticated.
-- Restrictive policies are AND-ed with the existing permissive ones, so this
-- can only take access away, never grant it. anon is not affected (its
-- policies never name authenticated); service_role and the server's owner
-- connection bypass RLS as before. `(SELECT public.mfa_satisfied())` is an
-- initplan: evaluated once per statement, not per row.
--
-- NOT covered here (recorded in docs/AUTH_AND_WEB_DEPLOY.md): the SECURITY
-- DEFINER client RPCs (block, DM request, presence, typing, …) run as their
-- owner, past RLS. A table created AFTER this file needs the policy too — the
-- watchdog check "every RLS table has mfa_required" flags one that lacks it.
--
-- Falsifier (as zz-lifecycle, whose factor is verified):
--   password token  -> GET /rest/v1/items?select=id   returns []
--   aal2 token      -> the same request returns their rows
--   simcheck (no factor), password token -> rows, as before.

CREATE OR REPLACE FUNCTION public.mfa_satisfied()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
      OR NOT EXISTS (
           SELECT 1 FROM auth.mfa_factors f
           WHERE f.user_id = auth.uid() AND f.status = 'verified'
         )
$$;

COMMENT ON FUNCTION public.mfa_satisfied() IS
  'True when the caller''s JWT is aal2 or the caller has no verified MFA factor. Used by the restrictive mfa_required policies (20260926b).';

-- Evaluated inside RLS as the CALLER (authenticated). anon never evaluates it
-- (the policies are TO authenticated), so it is not on the anon-callable list
-- the watchdog reviews.
REVOKE ALL ON FUNCTION public.mfa_satisfied() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.mfa_satisfied() TO authenticated, service_role;

DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND c.relrowsecurity
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS mfa_required ON public.%I', r.relname);
    EXECUTE format(
      'CREATE POLICY mfa_required ON public.%I AS RESTRICTIVE FOR ALL TO authenticated '
      'USING ((SELECT public.mfa_satisfied())) WITH CHECK ((SELECT public.mfa_satisfied()))',
      r.relname
    );
  END LOOP;
END $$;
