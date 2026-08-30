-- Reproduce a GoTrue user-delete AS GOTRUE'S OWN PRINCIPAL.
--
-- Why this file exists: on 2026-08-30 the delete was "verified" from a psql
-- superuser session, which proves nothing about supabase_auth_admin. The app
-- DSN cannot `SET ROLE supabase_auth_admin` ("permission denied to set role"),
-- so this has to run in the Supabase SQL Editor, which connects as `postgres`
-- and CAN assume the role.
--
-- SAFE: everything is inside a transaction that ends in ROLLBACK. No row is
-- actually deleted. Run the whole file at once.

BEGIN;

  -- Become the principal GoTrue actually uses.
  SET LOCAL ROLE supabase_auth_admin;

  SELECT current_user AS running_as;   -- must print supabase_auth_admin

  -- The delete GoTrue issues. Expect either success (then the 500 is NOT
  -- privileges) or the real "permission denied for table X" naming the first
  -- blocking cascade target.
  DELETE FROM auth.users
   WHERE id = '20503ad2-c62d-4700-810b-36da247bbf28';

ROLLBACK;   -- nothing above is kept
