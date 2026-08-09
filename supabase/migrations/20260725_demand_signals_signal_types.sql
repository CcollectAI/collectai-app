-- 2026-07-25: widen demand_signals.signal_type to every value the code emits.
--
-- The CHECK constraint permitted only 5 types:
--   mandate_created, search_query, item_viewed, price_alert_set, watchlist_add
-- while server/app + server/workers emit 23. Postgres rejected the other 18 on
-- every insert, so the whole data-moat capture layer was ~78% dead:
--
--   * item_added   -- 0 rows ever, despite 8 items created in the window. Its
--                     own call site calls it "strongest signal: user committed
--                     to adding this item" (intake_router.py:768).
--   * affiliate_click, feature_gated_attempt, subscription_purchased
--                  -- the monetization signals.
--   * item_scanned, catalog_browsed, category_viewed, no_results_search
--                  -- the product-gap signals.
--
-- Nothing surfaced it because record_demand_signal() catches the failure,
-- logs it as one warning among many, and returns False -- and every caller
-- ignores the return value (intake_router.py:779 is a bare `except: pass`).
--
-- Idempotent: drops then re-adds the constraint.

ALTER TABLE public.demand_signals
  DROP CONSTRAINT IF EXISTS demand_signals_signal_type_check;

ALTER TABLE public.demand_signals
  ADD CONSTRAINT demand_signals_signal_type_check
  CHECK (signal_type = ANY (ARRAY[
    -- original five
    'mandate_created',
    'search_query',
    'item_viewed',
    'price_alert_set',
    'watchlist_add',
    -- collection lifecycle
    'item_added',
    'item_scanned',
    'item_archived',
    'item_deleted',
    -- discovery
    'catalog_browsed',
    'category_viewed',
    'no_results_search',
    'marketplace_listing_viewed',
    -- events
    'event_viewed',
    'event_followed',
    'event_announcement_read',
    'ticket_clicked',
    -- watchlist / alerts
    'watchlist_remove',
    'price_alert_removed',
    'notification_settings_changed',
    -- monetization
    'affiliate_click',
    'feature_gated_attempt',
    'subscription_purchased'
  ]::text[]));

COMMENT ON CONSTRAINT demand_signals_signal_type_check ON public.demand_signals IS
  'Allowed signal types. MUST stay in sync with every record_demand_signal(signal_type=...) call site in server/app and server/workers — a value missing here is rejected at insert time and the caller swallows it.';
