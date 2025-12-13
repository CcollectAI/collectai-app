CREATE TABLE IF NOT EXISTS watchlist (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  nk text NOT NULL,
  est_value numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);

CREATE TABLE IF NOT EXISTS price_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nk text NOT NULL,
  q10 numeric,
  q50 numeric,
  q90 numeric,
  confidence numeric,
  comps_count integer,
  model_version text,
  source text,
  training_data_asof timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_preds_nk ON price_predictions(nk);
