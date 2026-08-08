-- Remove the price_drop/price_spike alert subsystem.
--
-- THE RULE IT FAILS
-- -----------------------------------------------------------------------------
-- An alert is only worth sending if it says: **the item you want is available,
-- right now, at or below the price you set.** That is the surviving predicate —
-- `url IS NOT NULL AND is_listing IS TRUE AND price_eur <= target_price` in
-- deal_discovery_worker._check_watchlist_snipes, branded "Target Hit".
--
-- `price_drop_30d` and `price_spike_7d` fire on a COMPUTED PRICE MOVEMENT. A
-- median that moved is not something you can buy. Waking someone for it is a
-- notification with no action, which is how users learn to ignore
-- notifications — the reasoning behind the 2026-08-06 consolidation that cut
-- eight alert workers to one (docs/alerts-and-insights.md).
--
-- WHAT WAS ACTUALLY IN THERE
-- -----------------------------------------------------------------------------
--   alerts_outbox           31 rows   27 price_drop_30d + 4 price_spike_7d,
--                                     2025-10-22 .. 2025-11-21
--   alert_delivery_queue    27 rows   ALL status='delivering', delivered_at NULL
--
-- So 27 alerts were queued for delivery in October 2025 and never delivered.
-- Nothing drains that queue — the drainer was removed with the rest of the
-- subsystem and the queue was left behind, which is why it looked alarming
-- (a queue with a writer and no reader is not the same as an unread log).
--
-- Checked before deleting: they are all price-movement alerts, so under the
-- rule above none of them should have been sent anyway. No user is owed a
-- notification here.
--
-- Also note `alert_delivery_queue.alert_id` is BIGINT while `public.alerts.id`
-- is UUID — the two cannot join. The queue keys on `alerts_outbox.id`, which
-- this migration removes with it.
--
-- WHAT THIS DOES NOT TOUCH
-- -----------------------------------------------------------------------------
-- * `alert_trigger_history` — LIVE. Target Hit writes it, the Home AlertsCard
--   reads it.
-- * `notification_history` — LIVE. The notifications screen reads it.
-- * `user_notifications` + the 15 guidance RPCs — a RECOMMENDATION engine
--   ("Best next add"), not an alert, so the rule above does not decide it. Its
--   cron (job 30) was disabled 2026-08-08 because it produced unbuyable,
--   unpriced suggestions; the scaffolding is left dormant pending a decision on
--   whether that feature is wanted at all.

BEGIN;

-- The trigger first: it is what couples the two tables.
DROP TRIGGER IF EXISTS trg_alerts_enqueue ON public.alerts_outbox;
DROP FUNCTION IF EXISTS public._alerts_enqueue();

-- The producers (their cron jobs 21 and 24 were already inactive) and the
-- janitor that has been cleaning an unwritten table daily (job 25 — unscheduled
-- separately, since cron.job is not writable from a migration).
DROP FUNCTION IF EXISTS public.produce_alerts_price_drop_30d();
DROP FUNCTION IF EXISTS public.produce_alerts_price_spike_7d();
DROP FUNCTION IF EXISTS public.cleanup_alerts_outbox(integer);

-- The DELIVERY machinery. The first attempt dropped only the four functions
-- above and failed on a dependency I had not enumerated (rpc_alert_attempt_start
-- depends on the queue's ROW TYPE, not just the table).
--
-- Verified before dropping: ZERO callers. None appear in the frontend's 16 real
-- supabase.rpc() names (checked with a local --dump-fe, not the four-month-stale
-- copy on EC2), and none is referenced in server/app or server/workers.
-- rpc_alerts_feed_for_user, rpc_alerts_list and rpc_get_alerts_recent READ like
-- live readers, which is exactly why they were checked rather than assumed.
--
-- HONEST NOTE ON WHAT ACTUALLY RAN: the signatures below were guessed and did
-- not all match, so several were no-ops and the CASCADE below did the real work.
-- What it reported dropping:
--     rpc_get_alerts_recent(integer)
--     rpc_alerts_list(uuid, text, timestamptz, integer)
--     rpc_alerts_feed_for_user(uuid, text, timestamptz, integer)
--     view v_alerts_pending          <- a dependent I never enumerated at all
--
-- Left as-is rather than rewritten to match, because the DROPs are idempotent
-- and the CASCADE is the part that is actually load-bearing. The lesson worth
-- keeping is the view: enumerating functions is not enumerating dependents.
DROP FUNCTION IF EXISTS public.rpc_alert_attempt_start(integer);
DROP FUNCTION IF EXISTS public.rpc_alert_attempt_finish(integer, boolean, text);
DROP FUNCTION IF EXISTS public.rpc_alerts_mark_delivered(bigint);
DROP FUNCTION IF EXISTS public.rpc_alert_targets(bigint);
DROP FUNCTION IF EXISTS public.rpc_alerts_feed_for_user(uuid, integer);
DROP FUNCTION IF EXISTS public.rpc_alerts_list(uuid);
DROP FUNCTION IF EXISTS public.rpc_get_alerts_recent(uuid, integer);

DROP TABLE IF EXISTS public.alert_delivery_queue CASCADE;
DROP TABLE IF EXISTS public.alerts_outbox CASCADE;

COMMIT;
