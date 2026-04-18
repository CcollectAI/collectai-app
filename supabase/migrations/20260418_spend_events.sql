-- Persistent spend tracking. In-memory spend_tracker resets on every bake
-- restart, so pre-launch we lost all monthly totals every time uvicorn
-- bounced. This table gives the tracker a durable store to survive restarts
-- and a historical log for admin dashboards.

CREATE TABLE IF NOT EXISTS public.spend_events (
    id          bigserial PRIMARY KEY,
    provider    text        NOT NULL,
    cost_eur    numeric(10,6) NOT NULL,
    ts          timestamptz NOT NULL DEFAULT now(),
    month_key   text        NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM'),
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_spend_events_month_provider
    ON public.spend_events (month_key, provider);

CREATE INDEX IF NOT EXISTS idx_spend_events_ts
    ON public.spend_events (ts DESC);

-- RLS: service_role only. Frontend should never read this directly — the
-- admin dashboard hits /admin/spend-summary which does its own ops auth.
ALTER TABLE public.spend_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "spend_events_service_only" ON public.spend_events;
CREATE POLICY "spend_events_service_only"
    ON public.spend_events
    USING (false);
