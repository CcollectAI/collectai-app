-- Performance indexes for data moat queries and deal discovery
-- Addresses supply/demand matview refresh range scans

BEGIN;

-- NOTE: price_predictions(item_ref) index is created in 20260228_data_moat_fixes.sql
-- which also adds the item_ref column itself.

-- supply_snapshots: index for matview refresh range scans
CREATE INDEX IF NOT EXISTS idx_supply_snapshots_snapshot_at
  ON public.supply_snapshots(snapshot_at DESC);

-- demand_signals: index for matview refresh range scans
CREATE INDEX IF NOT EXISTS idx_demand_signals_created_at
  ON public.demand_signals(created_at DESC);

COMMIT;
