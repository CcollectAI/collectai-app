-- 20260226_notification_preferences.sql
-- Add notification_preferences JSONB column to user_settings
-- Used by value_change_worker and insights_digest_worker to check user opt-in

ALTER TABLE public.user_settings
  ADD COLUMN IF NOT EXISTS notification_preferences JSONB NOT NULL DEFAULT '{
    "value_changes": true,
    "item_value_changes": true,
    "weekly_digest": true,
    "price_alerts": true,
    "deal_alerts": true,
    "chat_messages": true,
    "connection_requests": true,
    "event_announcements": true
  }'::jsonb;

COMMENT ON COLUMN public.user_settings.notification_preferences IS
  'JSONB object with boolean flags for each notification type. All default to true.';
