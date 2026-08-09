-- Restore the three push-engagement feedback tables.
--
-- I OVER-DELETED. `20260808_drop_guidance_notification_subsystem.sql` bundled
-- notification_impressions / _interactions / _outcomes into the guidance removal
-- because they carried an FK to `user_notifications`. Sharing a foreign key is
-- not the same as being the same feature, and I treated it as if it were.
--
-- They serve a DIFFERENT feature: the push engagement loop written by
-- `app/features/notification_feedback_router.py`, whose three endpoints are LIVE
-- and registered (`/notifications/feedback/{impression,interaction,outcome}` are
-- in the live OpenAPI). My "zero callers" check covered the RPCs and the
-- frontend; it did not cover a mounted FastAPI router writing raw SQL, and my
-- grep for the mount point missed it.
--
-- Dropping the tables under a live router left it 500-ing on every call, and
-- failed `preflight_router_drift` — which is a HARD gate, so the next bake
-- restart would have taken the API down.
--
-- Rebuilt from the router's own INSERT statements, which are authoritative for
-- the columns it writes. The FK to `user_notifications` is deliberately NOT
-- restored — that table is gone, and `notification_id` now refers to
-- `notification_history`, which is the store the live notifications screen
-- actually reads. Left unconstrained rather than pointed at a new parent,
-- because a FK asserting a relationship nobody has verified is how the original
-- confusion started.
--
-- Honest note on the feature itself: all three tables have been EMPTY since they
-- were created (2026-04-25, confirmed in the router's own docstring and again
-- today). The endpoints are live, the frontend has `logNotificationImpression` /
-- `Interaction` / `Outcome` in src/api/intelligenceApi.ts, and NO SCREEN CALLS
-- THEM. So the loop is built end-to-end and never wired to a tap.
--
-- That is a real gap and it is NOT fixed here — this migration only undoes my
-- overreach. Whether to wire the loop or delete the whole feature is a separate
-- decision, recorded in docs/alerts-and-insights.md.

BEGIN;

CREATE TABLE IF NOT EXISTS public.notification_impressions (
    notification_id  uuid        NOT NULL,
    user_id          uuid        NOT NULL,
    first_seen_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at     timestamptz NOT NULL DEFAULT now(),
    seen_count       integer     NOT NULL DEFAULT 1,
    client_context   jsonb,
    -- The router's ON CONFLICT target. Without this the upsert raises 42P10,
    -- which asyncpg surfaces and the handler swallows into {"ok": false} —
    -- a silent no-op (learning: check-upsert-targets.mjs exists for this).
    PRIMARY KEY (notification_id, user_id)
);

CREATE TABLE IF NOT EXISTS public.notification_interactions (
    id               bigserial   PRIMARY KEY,
    notification_id  uuid        NOT NULL,
    user_id          uuid        NOT NULL,
    kind             text        NOT NULL,
    occurred_at      timestamptz NOT NULL DEFAULT now(),
    meta             jsonb
);
CREATE INDEX IF NOT EXISTS idx_notification_interactions_user
    ON public.notification_interactions (user_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS public.notification_outcomes (
    id               bigserial   PRIMARY KEY,
    notification_id  uuid        NOT NULL,
    user_id          uuid        NOT NULL,
    outcome          text        NOT NULL,
    acted_at         timestamptz,
    latency_seconds  double precision,
    action_type      text,
    action_ref       jsonb,
    computed_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notification_outcomes_user
    ON public.notification_outcomes (user_id, computed_at DESC);

-- RLS: backend-only, same posture they had before. The client reaches these
-- through the router on the service role, never directly.
ALTER TABLE public.notification_impressions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outcomes     ENABLE ROW LEVEL SECURITY;

COMMIT;
