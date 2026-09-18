-- 2026-09-18: drop twelve fossil columns from public.items.
--
-- Class W (docs/CLASS_SWEEPS.md): columns whose names appear nowhere in the
-- code, which hold no data, and which no view or index depends on. Fossils of
-- abandoned features — the first attempt at build/paint tracking (which lives
-- on `build_paint_projects` now), a fraud-flagging pass, a checklist link, an
-- acquisition price superseded by `purchase_price`, and an identity lock.
--
-- WHAT WAS CHECKED BEFORE WRITING THIS, because a column drop is irreversible:
--
--   1. No CODE reference anywhere in the repo — not just `server/app` and
--      `src/`, which is the narrow scan that missed `items.fts` having a writer
--      in `services/collectors_merge/workers/build_fts_index.py`. The one hit
--      for `authenticity_score` is a mock object in a dev shell script, not
--      this column.
--   2. No VIEW depends on them (pg_depend through pg_rewrite). This is what
--      excluded seven others: `actual_price_eur` (items_scored),
--      `ai_estimate_usd` / `fts` / `latest_forecast` / `verified_date` /
--      `verified_price` (items_with_latest) and `prediction_confidence`
--      (api_user_analytics_v1). Those stay — dropping them needs CASCADE and a
--      view rebuild, which is real risk for no behaviour change.
--   3. No index on them (`fts` has a GIN index; none of these do).
--   4. EMPTY on production — asserted below rather than trusted, so this
--      migration refuses to run if any of them has acquired data since.
--
-- `identity_locked` is checked differently: it is NOT NULL-ish by default
-- (`false`), so counting non-nulls says 17 of 17. What matters is that no row
-- was ever actually locked.
--
-- ⚠️ AFTER APPLYING: regenerate scripts/schema.lock.json and DIFF it.
-- `preflight_schema_lock` is a blocking ExecStartPre — a stale lock means the
-- bake cannot come back up (docs/DEPLOYMENT.md §0b).

BEGIN;

DO $$
DECLARE
  populated text;
BEGIN
  SELECT string_agg(c, ', ') INTO populated FROM (
    SELECT 'acquisition_price'  AS c FROM public.items WHERE acquisition_price  IS NOT NULL
    UNION SELECT 'authenticity_score' FROM public.items WHERE authenticity_score IS NOT NULL
    UNION SELECT 'build_notes'        FROM public.items WHERE build_notes        IS NOT NULL
    UNION SELECT 'build_state'        FROM public.items WHERE build_state        IS NOT NULL
    UNION SELECT 'checklist_item_id'  FROM public.items WHERE checklist_item_id  IS NOT NULL
    UNION SELECT 'date_completed'     FROM public.items WHERE date_completed     IS NOT NULL
    UNION SELECT 'date_started'       FROM public.items WHERE date_started       IS NOT NULL
    UNION SELECT 'fraud_details'      FROM public.items WHERE fraud_details      IS NOT NULL
    UNION SELECT 'fraud_flags'        FROM public.items WHERE fraud_flags        IS NOT NULL
    UNION SELECT 'identity_locked'    FROM public.items WHERE identity_locked IS TRUE
    UNION SELECT 'identity_locked_at' FROM public.items WHERE identity_locked_at IS NOT NULL
    UNION SELECT 'paint_state'        FROM public.items WHERE paint_state        IS NOT NULL
  ) s;
  IF populated IS NOT NULL THEN
    RAISE EXCEPTION 'refusing to drop populated column(s): %', populated;
  END IF;
END $$;

ALTER TABLE public.items
  DROP COLUMN IF EXISTS acquisition_price,
  DROP COLUMN IF EXISTS authenticity_score,
  DROP COLUMN IF EXISTS build_notes,
  DROP COLUMN IF EXISTS build_state,
  DROP COLUMN IF EXISTS checklist_item_id,
  DROP COLUMN IF EXISTS date_completed,
  DROP COLUMN IF EXISTS date_started,
  DROP COLUMN IF EXISTS fraud_details,
  DROP COLUMN IF EXISTS fraud_flags,
  DROP COLUMN IF EXISTS identity_locked,
  DROP COLUMN IF EXISTS identity_locked_at,
  DROP COLUMN IF EXISTS paint_state;

DO $$
DECLARE remaining int;
BEGIN
  SELECT count(*) INTO remaining FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'items'
     AND column_name IN ('acquisition_price','authenticity_score','build_notes','build_state',
                         'checklist_item_id','date_completed','date_started','fraud_details',
                         'fraud_flags','identity_locked','identity_locked_at','paint_state');
  IF remaining > 0 THEN
    RAISE EXCEPTION '% column(s) survived the drop', remaining;
  END IF;
END $$;

COMMIT;
