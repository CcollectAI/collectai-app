-- Backstop the paired-column class on `items`.
--
-- The table deliberately carries both halves of three pairs, and different
-- readers key on different halves:
--   name            <-> title           Home portfolio / /portfolio/overview
--                                       read `name`; the Items tab falls back
--                                       to `title`.
--   purchased_at    <-> purchase_date   itemsProvider.ts:136 (ITEMS_SELECT)
--                                       reads `purchased_at`; the CSV export
--                                       (items_export_router.py:198) reads
--                                       `purchase_date`.
--   purchase_price  <-> purchase_price_eur
--                                       the analytics Cost Basis / DCA series
--                                       sums the EUR half.
--
-- Writing one half and not the other never throws: a SELECT of the unwritten
-- half returns NULL and every reader defaults (`?? 0`, 'Untitled'), so the
-- feature renders empty instead of failing. That is why this recurred — the
-- 2026-07-24 fix landed on add-manual.tsx and was never carried to the other
-- three writers (routes/items_router.py, features/import_router.py,
-- pipelines/seed_beta_users.py). Measured 2026-07-28 before this migration:
-- purchase_price_eur was non-null on 0 of 5 priced rows, and 5 of 14 rows had
-- a title with no name.
--
-- Fixing the writers one at a time is what failed. This trigger is the
-- chokepoint: whichever writer lands next, the row arrives complete.
--
-- NOTE on FX: the database cannot call the FX service, so this only derives
-- purchase_price_eur for the identity case (EUR, or currency unstated). A
-- non-EUR row still depends on the application converting -- see
-- app/lib/fx_service.py::convert_to_eur, wired into all three server writers.

CREATE OR REPLACE FUNCTION items_sync_paired_columns()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- name <-> title
    IF NULLIF(BTRIM(COALESCE(NEW.name, '')), '') IS NULL
       AND NULLIF(BTRIM(COALESCE(NEW.title, '')), '') IS NOT NULL THEN
        NEW.name := BTRIM(NEW.title);
    ELSIF NULLIF(BTRIM(COALESCE(NEW.title, '')), '') IS NULL
       AND NULLIF(BTRIM(COALESCE(NEW.name, '')), '') IS NOT NULL THEN
        NEW.title := BTRIM(NEW.name);
    END IF;

    -- purchased_at (timestamptz) <-> purchase_date (date).
    -- `date::timestamptz` resolves midnight in the SESSION timezone, so on an
    -- Amsterdam connection 2024-06-01 was stored as 2024-05-31 22:00Z and read
    -- back a day early in UTC. A purchase date has no time zone -- pin it to
    -- UTC midnight so the two columns always agree for every reader.
    -- Derive-only: an explicit purchased_at (watchlistProvider's "I Got It!"
    -- sends a real timestamp) is never overwritten.
    IF NEW.purchased_at IS NULL AND NEW.purchase_date IS NOT NULL THEN
        NEW.purchased_at := NEW.purchase_date::timestamp AT TIME ZONE 'UTC';
    ELSIF NEW.purchase_date IS NULL AND NEW.purchased_at IS NOT NULL THEN
        NEW.purchase_date := (NEW.purchased_at AT TIME ZONE 'UTC')::date;
    END IF;

    -- purchase_price -> purchase_price_eur, identity case only (see NOTE).
    IF NEW.purchase_price_eur IS NULL
       AND NEW.purchase_price IS NOT NULL
       AND COALESCE(UPPER(BTRIM(NEW.purchase_currency)), 'EUR') = 'EUR' THEN
        NEW.purchase_price_eur := NEW.purchase_price;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_items_sync_paired_columns ON public.items;

-- BEFORE INSERT OR UPDATE, and deliberately unconditional on UPDATE: a patch
-- that sets only `title` must carry `name` along with it, same as an insert.
-- Ordered after trg_items_canonical_ref alphabetically is irrelevant here --
-- these columns are untouched by the canonical-ref resolver.
CREATE TRIGGER trg_items_sync_paired_columns
    BEFORE INSERT OR UPDATE ON public.items
    FOR EACH ROW
    EXECUTE FUNCTION items_sync_paired_columns();

-- Backfill the rows that predate the trigger.
UPDATE items
   SET name = BTRIM(title)
 WHERE NULLIF(BTRIM(COALESCE(name, '')), '') IS NULL
   AND NULLIF(BTRIM(COALESCE(title, '')), '') IS NOT NULL;

UPDATE items
   SET title = BTRIM(name)
 WHERE NULLIF(BTRIM(COALESCE(title, '')), '') IS NULL
   AND NULLIF(BTRIM(COALESCE(name, '')), '') IS NOT NULL;

UPDATE items
   SET purchased_at = purchase_date::timestamp AT TIME ZONE 'UTC'
 WHERE purchased_at IS NULL AND purchase_date IS NOT NULL;

UPDATE items
   SET purchase_date = (purchased_at AT TIME ZONE 'UTC')::date
 WHERE purchase_date IS NULL AND purchased_at IS NOT NULL;

-- Re-pin rows already stored at local midnight (the pre-fix cast), which read
-- back a day early in UTC. Only touches rows whose purchased_at is exactly the
-- local-midnight rendering of purchase_date -- a real time-of-day is left be.
UPDATE items
   SET purchased_at = purchase_date::timestamp AT TIME ZONE 'UTC'
 WHERE purchase_date IS NOT NULL
   AND purchased_at IS NOT NULL
   AND purchased_at <> purchase_date::timestamp AT TIME ZONE 'UTC'
   AND (purchased_at AT TIME ZONE 'UTC')::date
       BETWEEN purchase_date - 1 AND purchase_date + 1;

UPDATE items
   SET purchase_price_eur = purchase_price
 WHERE purchase_price_eur IS NULL
   AND purchase_price IS NOT NULL
   AND COALESCE(UPPER(BTRIM(purchase_currency)), 'EUR') = 'EUR';
