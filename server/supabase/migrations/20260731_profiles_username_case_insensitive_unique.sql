-- Enforce username uniqueness case-INSENSITIVELY in the database.
--
-- `profiles_username_key` is UNIQUE (username) — case-sensitive — so the DB
-- would happily store `Merle` alongside `merle`. Two places compensated in
-- application code:
--
--   * `handle_new_user` (signup trigger) checks `lower(p.username) = lower(uname)`
--   * `PATCH /settings/profile` (added 2026-07-31) does the same before UPDATE
--
-- That is the pattern this codebase keeps getting burned by: a constraint
-- narrower than what the code assumes. Any writer that skips the check — a
-- backfill, an admin tool, direct SQL, a future endpoint — silently creates a
-- collision, and both compensating checks are read-then-write races besides.
--
-- There was already an index on `lower(username)`; it was simply not UNIQUE.
-- This replaces it with a unique one, so the database is the authority and the
-- application checks become a backstop that produces a friendly 409 instead of
-- a raw 23505.
--
-- Safe to apply: verified 0 case-collisions on prod beforehand
--   SELECT lower(username), count(*) FROM profiles WHERE username IS NOT NULL
--    GROUP BY 1 HAVING count(*) > 1;   -- empty
--
-- NULLs are unaffected: multiple profiles may have username IS NULL, which is
-- the current state for every legacy row (24 of 24).
--
-- Both compensating paths already handle the violation correctly:
--   * handle_new_user catches unique_violation and falls back to a nameless
--     profile rather than failing signup
--   * update_profile catches asyncpg.UniqueViolationError -> 409 USERNAME_TAKEN

BEGIN;

DROP INDEX IF EXISTS public.profiles_username_citrix;

CREATE UNIQUE INDEX IF NOT EXISTS profiles_username_lower_key
    ON public.profiles (lower(username));

COMMIT;
