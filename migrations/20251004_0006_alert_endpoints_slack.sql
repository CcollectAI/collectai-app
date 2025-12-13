-- no-op placeholder; earlier code accepts 'slack' kind. Ensure index exists.
CREATE INDEX IF NOT EXISTS idx_alert_endpoints_user_kind ON alert_endpoints(user_id, kind);
