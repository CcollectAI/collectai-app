-- 2026-09-18: drop marketplace_listings.reports_count.
--
-- Written by `report_listing` on every new report, and READ BY NOTHING — not
-- the server, not the app, not the ops moderation queue. It appeared only in
-- the schema dumps.
--
-- And it could not have been used as it stood: nothing ever decremented it, so
-- it counted reports EVER FILED, while every consumer that matters counts
-- reports still OPEN. Both of those consumers already derive the honest number
-- from the table the DSA obligations attach to:
--
--   * the ops alert   -- count(*) FROM listing_reports WHERE status = 'open'
--   * /ops/listing-reports -- reads listing_reports directly, oldest first
--
-- A denormalised copy that disagrees with its source by construction is worse
-- than no copy: the next person to reach for it would read "3" on a listing
-- whose reports were all resolved. Dropped rather than fixed, because fixing it
-- means maintaining a counter that duplicates a count(*) over an indexed table
-- with 0 rows today.
--
-- The report data itself is untouched — `listing_reports` is the artifact, and
-- this only removes the tally beside it.
--
-- ⚠️ AFTER APPLYING: regenerate scripts/schema.lock.json and diff it. The lock
-- pins this column, `preflight_schema_lock` is a BLOCKING ExecStartPre, and a
-- stale lock means the bake cannot come back up. See docs/DEPLOYMENT.md §0b.

BEGIN;

ALTER TABLE public.marketplace_listings DROP COLUMN IF EXISTS reports_count;

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'marketplace_listings'
       AND column_name = 'reports_count'
  ) THEN
    RAISE EXCEPTION 'reports_count still present';
  END IF;
END $$;

COMMIT;
