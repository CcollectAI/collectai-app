-- 2026-07-25 (b): three more CHECK constraints narrower than what the code emits.
--
-- Same class as 20260725_demand_signals_signal_types.sql: Postgres rejects the
-- insert, the caller swallows the failure, and the feature is silently dead.
-- Found by sweeping every enum-like CHECK constraint against the string
-- literals the code actually writes to that column.

-- 1. demand_signals.signal_type — CORRECTS the earlier migration in this pair.
--    That one derived its list by grepping call sites and missed three types.
--    app/features/data_moat.py holds the authoritative `valid_types` set (26):
--    record_demand_signal() rejects anything outside it BEFORE the insert, so
--    the DB constraint should mirror that set exactly, no wider and no
--    narrower. Missing here were:
--      collection_viewed
--      paywall_viewed / paywall_dismissed  -- read by
--        intelligence_router.py:666-671 for /intelligence/top-paywall-
--        rejections, so that whole paywall funnel could never have data.
ALTER TABLE public.demand_signals
  DROP CONSTRAINT IF EXISTS demand_signals_signal_type_check;

ALTER TABLE public.demand_signals
  ADD CONSTRAINT demand_signals_signal_type_check
  CHECK (signal_type = ANY (ARRAY[
    'affiliate_click','catalog_browsed','category_viewed','collection_viewed',
    'event_announcement_read','event_followed','event_viewed',
    'feature_gated_attempt','item_added','item_archived','item_deleted',
    'item_scanned','item_viewed','mandate_created','marketplace_listing_viewed',
    'no_results_search','notification_settings_changed','paywall_dismissed',
    'paywall_viewed','price_alert_removed','price_alert_set','search_query',
    'subscription_purchased','ticket_clicked','watchlist_add','watchlist_remove'
  ]::text[]));

COMMENT ON CONSTRAINT demand_signals_signal_type_check ON public.demand_signals IS
  'MUST mirror valid_types in server/app/features/data_moat.py exactly. A value present in code but absent here is rejected at insert time and swallowed by the caller.';

-- 2. notification_outcomes.outcome
--    src/lib/notificationOutcomeTracker.ts:60 writes "converted", and
--    src/api/intelligenceApi.ts:43 types the union as
--    "converted" | "ignored" | "expired" | "other". Only 'ignored' was
--    permitted, so every converted/expired/other push outcome was rejected --
--    the push feedback loop could only ever record non-conversions, which
--    biases any ranking built on it. Existing values kept.
ALTER TABLE public.notification_outcomes
  DROP CONSTRAINT IF EXISTS notification_outcomes_outcome_check;

ALTER TABLE public.notification_outcomes
  ADD CONSTRAINT notification_outcomes_outcome_check
  CHECK (outcome = ANY (ARRAY[
    'acted','ignored','superseded','no_action_expected',
    'converted','expired','other'
  ]::text[]));

-- 3. activity_feed.activity_type
--    app/(auth)/onboarding.tsx:330 posts 'onboarding_completed' via
--    POST /activity/log. It was not in the allowed list, so the ONLY thing
--    that writes activity_feed was rejected every time -- which is why the
--    table has 0 rows despite 23 users.
ALTER TABLE public.activity_feed
  DROP CONSTRAINT IF EXISTS activity_feed_activity_type_check;

ALTER TABLE public.activity_feed
  ADD CONSTRAINT activity_feed_activity_type_check
  CHECK (activity_type = ANY (ARRAY[
    'item_added','item_sold','event_rsvp','event_created','project_completed',
    'achievement_earned','category_followed','collection_milestone',
    'onboarding_completed'
  ]::text[]));
