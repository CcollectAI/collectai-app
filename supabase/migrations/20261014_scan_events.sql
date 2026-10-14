-- One row per QuickScan, with what it produced (2026-10-14).
--
-- WHY: nothing recorded a scan's OUTCOME. `demand_signals.item_scanned` holds
-- the request's category HINT (empty on 37 of 52 rows) and no result;
-- `predict_sessions` looked like scan history but is written only by the
-- Sanity E2E workflow (row times match the CI runs to the second) -- no app
-- code calls the predict-* edge functions. So "is QuickScan accurate, fast,
-- and does a scan become an item?" could not be answered from the server.
--
-- Written by server/app/agents/intake_router.py::intake_image_only (the
-- endpoint the app's QuickScan uses, via src/api/intakeApi.ts) on success AND
-- on failure. A saved scan is visible as items.source = 'quickscan'.
--
-- Server-only: RLS on with no policies, and no grants to anon/authenticated
-- (the API writes through its own pool, which bypasses RLS).
CREATE TABLE IF NOT EXISTS public.scan_events (
  id             bigserial PRIMARY KEY,
  user_id        uuid,
  created_at     timestamptz NOT NULL DEFAULT now(),
  outcome        text NOT NULL CHECK (outcome IN ('identified', 'failed')),
  category       text,
  category_confidence real,
  item_key       text,
  catalog_matched boolean,
  identification_method text,
  price_mid_eur  numeric,
  price_source   text,
  duration_ms    integer,
  error          text
);

CREATE INDEX IF NOT EXISTS scan_events_created_at_idx ON public.scan_events (created_at DESC);
CREATE INDEX IF NOT EXISTS scan_events_user_idx ON public.scan_events (user_id, created_at DESC);

ALTER TABLE public.scan_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.scan_events FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE public.scan_events_id_seq FROM PUBLIC, anon, authenticated;
