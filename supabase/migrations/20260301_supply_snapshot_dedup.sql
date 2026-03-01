-- Supply snapshot dedup: index to accelerate the NOT EXISTS check
-- in record_supply_snapshot() that prevents duplicates within the same hour.
-- Also doubles as a covering index for supply trend queries.

CREATE INDEX IF NOT EXISTS idx_supply_snapshots_dedup_lookup
    ON public.supply_snapshots (category, item_key, source, snapshot_at DESC);
