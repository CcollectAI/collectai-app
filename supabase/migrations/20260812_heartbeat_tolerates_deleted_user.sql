-- rpc_heartbeat_v1: don't write presence for a user that no longer exists.
--
-- The 2026-08-12 watchdog reported, as `high`, 30 rejected writes in 24h:
--
--   insert or update on table "user_presence" violates foreign key constraint
--   "user_presence_user_id_fkey"
--   Key (user_id)=(92416ed4-b8ad-4cc1-a258-1519d1d498af) is not present in table "users".
--
-- All 30 are the SAME uid, and that uid exists in no table — not auth.users,
-- not profiles, not items. It is a DELETED account whose client is still signed
-- in and still heart-beating (~every 48 min). `user_presence.user_id` is
-- `REFERENCES auth.users(id) ON DELETE CASCADE`, so the row went away with the
-- account and every heartbeat since has been rejected.
--
-- A JWT can outlive the account it names. That is normal — the token stays
-- valid until it expires, and the device has no way to know the account was
-- deleted until something it calls fails. Presence is a cosmetic online dot, so
-- the correct behaviour for it is to do nothing, not to raise: one stale device
-- should not be able to write 30 ERROR lines a day into the Postgres log, where
-- they are indistinguishable from a real constraint bug and page the watchdog
-- daily. A daily false `high` is how the channel stops being read.
--
-- Deliberately silent rather than RAISE WARNING: logging it would move the noise
-- rather than remove it, and the condition is expected, not exceptional. The
-- account's real problems (its authed reads returning nothing) surface on their
-- own. The NULL guard is included for the same reason — an anon caller reaching
-- this RPC should be a no-op, not a NOT NULL violation.

CREATE OR REPLACE FUNCTION public.rpc_heartbeat_v1()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  uid uuid := auth.uid();
BEGIN
  IF uid IS NULL OR NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = uid) THEN
    RETURN;
  END IF;

  INSERT INTO user_presence (user_id, last_seen_at, is_online, updated_at)
  VALUES (uid, now(), true, now())
  ON CONFLICT (user_id)
  DO UPDATE SET last_seen_at = now(), is_online = true, updated_at = now();
END;
$function$;
