-- Account deletion must not be blocked by a user's own rows.
--
-- Measured on prod 2026-08-30: ten tables reference auth.users with NO ACTION,
-- so a row in any of them makes DELETE FROM auth.users raise a foreign-key
-- violation. GoTrue surfaces that as a 500 — which is how the sanity-e2e
-- workflow had been failing on every push, and what would have met the first
-- member who filed a report or authored an announcement.
--
--   select conrelid::regclass, conname, confdeltype from pg_constraint
--    where contype='f' and confrelid='auth.users'::regclass
--      and confdeltype not in ('c','n');
--
-- Five were already cleared by app/routes/account_router.py. Three more join it
-- in the same change; the remaining two are deliberately left:
--
--   chat_rooms        orphan table — no writer anywhere in the repo, so no row
--                     can ever exist to block anything
--   sponsor_companies future product, 0 rows. Deleting a company because its
--                     admin left is the wrong semantics; it wants reassignment,
--                     which is a product decision and not this migration's.
--
-- CASCADE, not SET NULL, for two reasons:
--   1. chat_reports.reporter and event_announcements.author_user_id are NOT
--      NULL, so SET NULL is not available without also relaxing the column.
--   2. CASCADE makes the database do exactly what _ALLOWED_TABLES already does
--      in the application path. App and schema then agree, instead of the DB
--      keeping rows the code deletes.
--
-- All three tables held 0 rows at time of writing except task_queue (1, the
-- e2e test user), so this is a latent fix, not a repair.
--
-- Idempotent: each constraint is dropped IF EXISTS before being re-added.

BEGIN;

ALTER TABLE public.task_queue
  DROP CONSTRAINT IF EXISTS task_queue_created_by_fkey;
ALTER TABLE public.task_queue
  ADD CONSTRAINT task_queue_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.chat_reports
  DROP CONSTRAINT IF EXISTS chat_reports_reporter_fkey;
ALTER TABLE public.chat_reports
  ADD CONSTRAINT chat_reports_reporter_fkey
  FOREIGN KEY (reporter) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.event_announcements
  DROP CONSTRAINT IF EXISTS event_announcements_author_user_id_fkey;
ALTER TABLE public.event_announcements
  ADD CONSTRAINT event_announcements_author_user_id_fkey
  FOREIGN KEY (author_user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- Post-write assertion: refuse to report success if any of the three is still
-- NO ACTION. A migration that silently no-ops is worse than one that fails.
DO $$
DECLARE bad int;
BEGIN
  SELECT count(*) INTO bad
    FROM pg_constraint
   WHERE contype = 'f'
     AND confrelid = 'auth.users'::regclass
     AND conrelid IN ('public.task_queue'::regclass,
                      'public.chat_reports'::regclass,
                      'public.event_announcements'::regclass)
     AND confdeltype <> 'c';
  IF bad > 0 THEN
    RAISE EXCEPTION 'FK delete action not applied on % constraint(s)', bad;
  END IF;
END $$;

COMMIT;
