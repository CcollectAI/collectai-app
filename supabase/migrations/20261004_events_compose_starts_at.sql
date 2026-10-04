-- events.starts_at had no writer for member-created events.
--
-- The scrapers compose it in Python (newsletter_scraper._compose_starts_at:
-- date + optional time, read as UTC, date-only -> midnight). None of the
-- member paths did: events_core create / edit / duplicate and the two
-- sponsor_company_router INSERTs all write `date` and `time` and never
-- `starts_at`. The five older member rows only have it because of a one-off
-- backfill; the first member event created after it (2026-09-27) landed NULL
-- and the watchdog has paged "events have a date but no starts_at" daily
-- since 09-28.
--
-- One chokepoint instead of five call sites. The trigger only FILLS: it never
-- overwrites a starts_at the writer supplied, so the scrapers keep their own
-- value. On UPDATE it recomputes when date/time changed and the writer did not
-- also set starts_at — otherwise an edited date would leave a stale timestamp.
--
-- search_path is two UNQUOTED schemas on purpose (class M, 20260917b).

CREATE OR REPLACE FUNCTION public.events_compose_starts_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF NEW.date IS NULL THEN
    RETURN NEW;
  END IF;
  IF NEW.starts_at IS NULL
     OR (TG_OP = 'UPDATE'
         AND (NEW.date IS DISTINCT FROM OLD.date OR NEW.time IS DISTINCT FROM OLD.time)
         AND NEW.starts_at IS NOT DISTINCT FROM OLD.starts_at) THEN
    NEW.starts_at := (NEW.date + COALESCE(NEW.time, time '00:00')) AT TIME ZONE 'UTC';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_events_compose_starts_at ON public.events;
CREATE TRIGGER trg_events_compose_starts_at
  BEFORE INSERT OR UPDATE OF date, time, starts_at ON public.events
  FOR EACH ROW EXECUTE FUNCTION public.events_compose_starts_at();

-- Backfill through the trigger, then refuse to report success if anything
-- is left behind.
UPDATE public.events SET starts_at = NULL
 WHERE date IS NOT NULL AND starts_at IS NULL;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM public.events WHERE date IS NOT NULL AND starts_at IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION 'events_compose_starts_at: % dated row(s) still lack starts_at', n;
  END IF;
END $$;
