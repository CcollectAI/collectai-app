-- Remove the DB-side guidance / in-app-inbox subsystem.
--
-- WHY IT GOES
-- -----------------------------------------------------------------------------
-- Merle's rule for alerts: if it does not say "the item you want is available at
-- the price you want", it is pointless as an alert. This subsystem is not even
-- that — it is a RECOMMENDATION engine ("Best next add"). It goes for a
-- different reason, which is stronger: **it has never been read, and what it
-- produces is wrong.**
--
--   188 rows since 2026-01-24
--       0 read
--       0 read_at
--       0 dismissed
--
-- Seven months of daily writes and the engagement columns have never moved once.
-- That is proof of no reader, not a failed grep. `grep` agrees: zero callers for
-- any of the 17 functions across app/, src/ and server/.
--
-- And the output is not worth wiring up. The newest rows, three days running,
-- identical:
--
--     title    Best next add
--     body     BE@RBRICK 100% / 400%
--     why      "Missing from your collection; no recent listings yet."
--     signals  listings_7d: 0, listings_30d: 0, median_price_eur_30d: null
--
-- It recommends an item with ZERO availability and NO price, and the same one
-- every day. "Buy this thing you cannot buy and we cannot price" is worse than
-- silence, so shipping the UI would have made the app worse, not better.
--
-- WHY DELETE RATHER THAN LEAVE DORMANT
-- -----------------------------------------------------------------------------
-- Dormant code is not free. It kept `user_notifications` in the RLS audit, in
-- the account-deletion audit, in schema.lock and in the orphan-store audit —
-- four gates carrying a permanent entry that a reader has to recognise as
-- expected. That is exactly how a gate stops being read.
--
-- Recoverable: this migration is in git, and every function body is in the
-- database's own history. If a "what should I buy next" feature is ever wanted,
-- it needs the RANKING rewritten anyway (availability must DISQUALIFY a
-- suggestion, not annotate it), and the scaffolding is the cheap half.
--
-- pg_cron job 30, which drove it daily at 09:00 UTC, was disabled 2026-08-08 and
-- is unscheduled alongside this (cron.job is not writable from a migration).
--
-- NOT TOUCHED
-- -----------------------------------------------------------------------------
-- `alert_trigger_history` and `notification_history` are the LIVE path — Target
-- Hit writes the first and the Home AlertsCard reads it; notify_user writes the
-- second and app/notifications.tsx reads it. Neither is involved here.

BEGIN;

-- Emitters (writers).
DROP FUNCTION IF EXISTS public.rpc_emit_smart_guidance_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_emit_next_best_add_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_emit_progress_guidance_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_emit_event_notifications_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_emit_event_reminders_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_emit_event_reminders_dev_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_wishlist_compute_alerts_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_wishlist_compute_alerts_dev_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_wishlist_compute_availability_alerts_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_wishlist_compute_availability_alerts_dev_v1(uuid);

-- Readers / mutators. None is in the frontend's 16 real supabase.rpc() names,
-- checked with a local --dump-fe rather than the stale copy on EC2.
DROP FUNCTION IF EXISTS public.rpc_user_inbox_v1(uuid, integer);
DROP FUNCTION IF EXISTS public.rpc_get_what_matters_now_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_get_what_matters_now_dev_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_mark_notification_read_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_dismiss_notification_v1(uuid);
DROP FUNCTION IF EXISTS public.rpc_compute_notification_outcomes_v1();
DROP FUNCTION IF EXISTS public.rpc_compute_notification_outcomes_v2();

-- CASCADE because the last cleanup taught the lesson: enumerating FUNCTIONS is
-- not enumerating DEPENDENTS. That drop reported a view (v_alerts_pending) I had
-- never looked for. Anything CASCADE reports here is listed in the commit.
DROP TABLE IF EXISTS public.user_notifications CASCADE;

-- The idempotency ledger for cron job 30. Its ONLY purpose was that job's
-- `NOT EXISTS ... AND run_date = current_date` guard, so it has no meaning once
-- the job and the emitter are gone.
DROP TABLE IF EXISTS public.guidance_runs CASCADE;

-- ---------------------------------------------------------------------------
-- ROUND 2. The DROPs above used GUESSED signatures and 13 functions survived —
-- rpc_emit_event_reminders_v1 takes (interval), not (uuid); the outcome
-- computers take (uuid, interval, interval). `DROP FUNCTION` matches on the
-- full signature, so a wrong guess is a SILENT no-op, which is precisely the
-- shape of failure this codebase keeps finding. Dropped by identity instead.
--
-- The three analytics sinks go too: their FK to user_notifications was just
-- CASCADE-dropped, so `notification_id` now references nothing. All three are
-- empty (0 rows) and their only writers/readers were the RPCs above.
-- ---------------------------------------------------------------------------
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS sig
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND (p.proname LIKE 'rpc_emit_event_reminders%'
        OR p.proname LIKE 'rpc_get_what_matters_now%'
        OR p.proname LIKE 'rpc_wishlist_compute_%'
        OR p.proname LIKE 'rpc_compute_notification_outcomes%'
        OR p.proname LIKE 'rpc_log_notification_%')
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
  END LOOP;
END $$;

DROP TABLE IF EXISTS public.notification_impressions CASCADE;
DROP TABLE IF EXISTS public.notification_interactions CASCADE;
DROP TABLE IF EXISTS public.notification_outcomes CASCADE;

COMMIT;
