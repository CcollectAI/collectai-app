CREATE TABLE IF NOT EXISTS alert_endpoints (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('webhook')),
  url text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alert_endpoints_user ON alert_endpoints(user_id);
