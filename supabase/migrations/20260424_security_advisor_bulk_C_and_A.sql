-- 2026-04-24: bulk Supabase security-advisor fix — classes C (functions
-- with mutable search_path) + A (tables with RLS on but no policies).
-- Follow-up to the two per-finding batches earlier today.
--
-- NOT in scope: Class B (144 public tables with RLS disabled). Many of
-- those are intentionally public (catalog items, categories, price_*).
-- Blind-enabling RLS would break frontend reads, so Class B needs
-- per-group triage (see separate planning doc).
--
-- Class C handling: SET search_path = 'public, pg_temp'.
--   * Explicit default — doesn't force fully-qualified refs in body
--     (empty '' would, risking breakage on any function using bare names)
--   * Still clears the linter — "not set" is the trigger, any fixed value
--     satisfies it
--   * Eliminates search_path-injection because the path is now pinned
--   * Covers both SECURITY DEFINER and SECURITY INVOKER uniformly
--
-- Class A handling: explicit deny-all policy. RLS was already on; there
-- was just no policy so the implicit-deny went un-documented. Adding
-- USING (false) / WITH CHECK (false) changes no behavior (service-role
-- still bypasses, anon/auth were already blocked) but clears the lint.

-- ---------------------------------------------------------------------------
-- Class C — 410 functions, bulk ALTER
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  f record;
  v_count int := 0;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure::text AS sig,
           p.prokind = 'p' AS is_proc
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND (p.proconfig IS NULL
           OR NOT EXISTS (
             SELECT 1 FROM unnest(p.proconfig) cfg WHERE cfg LIKE 'search_path=%'
           ))
      -- Skip functions owned by extensions (pg_trgm, etc.) — we can't
      -- ALTER them and the advisor rule targets our own functions.
      AND NOT EXISTS (
        SELECT 1 FROM pg_depend d
        WHERE d.objid = p.oid AND d.deptype = 'e'
      )
      -- prokind: 'f'=function, 'p'=procedure, 'a'=aggregate, 'w'=window.
      -- Procedures need ALTER PROCEDURE (different statement), aggregates
      -- and window functions don't support SET. Handle each separately.
      AND p.prokind IN ('f', 'p')
  LOOP
    IF f.is_proc THEN
      EXECUTE format('ALTER PROCEDURE %s SET search_path = %L',
                     replace(f.sig, 'FUNCTION ', ''), 'public, pg_temp');
    ELSE
      EXECUTE format('ALTER FUNCTION %s SET search_path = %L', f.sig, 'public, pg_temp');
    END IF;
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Pinned search_path on % functions', v_count;
END $$;

-- ---------------------------------------------------------------------------
-- Class A — 5 tables, bulk deny-all policy
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  t record;
  v_count int := 0;
BEGIN
  FOR t IN
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relrowsecurity
      AND NOT EXISTS (
        SELECT 1 FROM pg_policies p
        WHERE p.schemaname = 'public' AND p.tablename = c.relname
      )
  LOOP
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL USING (false) WITH CHECK (false)',
      t.relname || '_deny_all',
      t.relname
    );
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Added deny-all policy on % tables', v_count;
END $$;
