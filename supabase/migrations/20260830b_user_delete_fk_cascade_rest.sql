-- Part 2: a direct DELETE FROM auth.users must also succeed.
--
-- 20260830_user_delete_fk_cascade.sql cascaded the three tables the application
-- deletion path did NOT clear, on the reasoning that the other five were
-- "already handled". That reasoning was wrong, and the e2e proved it:
--
--   violates foreign key constraint "user_category_follows_user_id_fkey"
--   DETAIL: Key (id)=(20503ad2-…) is still referenced from user_category_follows
--
-- user_category_follows IS in _ALLOWED_TABLES. That makes OUR endpoint work.
-- It does nothing for a delete issued through GoTrue's admin API — which is
-- what the Supabase dashboard uses, what the sanity-e2e workflow uses, and
-- what any operator reaching for "delete this user" will use.
--
-- Being cleared by the app path and not blocking a direct delete are two
-- different guarantees. The application cleanup stays (it controls WHAT is
-- erased and in what order); these constraints make the row removable at all.
--
-- sponsor_companies is deliberately NOT cascaded: deleting a company because
-- its admin closed their account is the wrong semantics — it wants
-- reassignment, which is a product decision. It holds 0 rows, so it blocks
-- nothing today, and it is the one remaining NO ACTION FK by choice.

BEGIN;

ALTER TABLE public.user_category_follows
  DROP CONSTRAINT IF EXISTS user_category_follows_user_id_fkey;
ALTER TABLE public.user_category_follows
  ADD CONSTRAINT user_category_follows_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.portfolio_values
  DROP CONSTRAINT IF EXISTS portfolio_values_user_id_fkey;
ALTER TABLE public.portfolio_values
  ADD CONSTRAINT portfolio_values_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.chat_messages
  DROP CONSTRAINT IF EXISTS chat_messages_user_id_fkey;
ALTER TABLE public.chat_messages
  ADD CONSTRAINT chat_messages_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.event_templates
  DROP CONSTRAINT IF EXISTS event_templates_user_id_fkey;
ALTER TABLE public.event_templates
  ADD CONSTRAINT event_templates_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.event_announcement_reads
  DROP CONSTRAINT IF EXISTS event_announcement_reads_user_id_fkey;
ALTER TABLE public.event_announcement_reads
  ADD CONSTRAINT event_announcement_reads_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.chat_rooms
  DROP CONSTRAINT IF EXISTS chat_rooms_created_by_fkey;
ALTER TABLE public.chat_rooms
  ADD CONSTRAINT chat_rooms_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE CASCADE;

-- Post-write assertion: sponsor_companies is the ONLY NO ACTION FK left, and
-- that is a decision. Anything else means this migration did not do its job.
DO $$
DECLARE bad text;
BEGIN
  SELECT string_agg(conrelid::regclass::text, ', ') INTO bad
    FROM pg_constraint
   WHERE contype = 'f'
     AND confrelid = 'auth.users'::regclass
     AND confdeltype NOT IN ('c', 'n')
     AND conrelid <> 'public.sponsor_companies'::regclass;
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'still NO ACTION on: %', bad;
  END IF;
END $$;

COMMIT;
