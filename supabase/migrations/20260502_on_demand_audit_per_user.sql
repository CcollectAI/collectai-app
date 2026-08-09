-- Per-user audit log for /enrich/on-demand calls.
--
-- Pre-2026-05-02 enrich_router.py applied a single GLOBAL daily cap
-- (5000 calls/day across the whole org) and ignored the per-tier limits
-- {"free": 5, "pro": 50, "premium": 200} that were documented in
-- RATE_LIMITS_BY_TIER. A single Pro user could exhaust the entire
-- org's daily quota and lock everyone else out.
--
-- The existing `on_demand_lookups` table is keyed on item_ref (one row
-- per item, multiple users hitting the same item just bump fetch_count),
-- so it can't be used for per-user counting. This audit table writes one
-- row per call with the user_id, allowing per-user daily caps via a
-- simple COUNT(*) query.

CREATE TABLE IF NOT EXISTS public.on_demand_lookups_audit (
    id          bigserial PRIMARY KEY,
    user_id     uuid NOT NULL,
    item_ref    text NOT NULL,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    cost_cents  integer NOT NULL DEFAULT 0,
    provider    text  -- 'scrapedo' | 'claude_estimate' | 'cache_hit'
);

-- Per-user recent-window count is the hot query. Sized to handle:
--   ~200 calls/day × Premium users at peak load.
-- The DESC index on fetched_at keeps the cap-check a single index scan.
CREATE INDEX IF NOT EXISTS idx_on_demand_audit_user_recent
    ON public.on_demand_lookups_audit (user_id, fetched_at DESC);

-- RLS: users can read their own audit rows (for "X/Y used today" UI).
-- Service role writes; only authenticated users can read their own.
ALTER TABLE public.on_demand_lookups_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS on_demand_audit_select_own ON public.on_demand_lookups_audit;
CREATE POLICY on_demand_audit_select_own ON public.on_demand_lookups_audit
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

COMMENT ON TABLE public.on_demand_lookups_audit IS
    'One row per /enrich/on-demand call. Used for per-user daily cap enforcement (5/50/200 by tier) and for the "X/Y used today" hint in the FE.';
